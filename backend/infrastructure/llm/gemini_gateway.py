"""
Adaptador del puerto LlmGateway para Google Gemini (SDK oficial google-genai).

Responsabilidades:
- Timeout explicito por llamada (AI_TIMEOUT_SECONDS).
- Reintentos con backoff exponencial + jitter ante 429 (rate limit) y 503
  (modelo sobrecargado), hasta AI_MAX_RETRIES reintentos.
- Traducir los fallos a las excepciones del dominio, que la API mapea a HTTP:
    LlmNotConfigured -> 503   LlmTimeout -> 504
    LlmRateLimited   -> 429   LlmProviderError -> 502
- Medir latencia y tokens (entrada, salida y "thinking").

La configuracion se lee en cada llamada desde `settings` (inyectado por
bootstrap.py), asi un cambio en app.config se respeta sin reconstruir nada.
Las pruebas reemplazan `_call_model` con monkeypatch: el resto del flujo
(reintentos, mapeo de errores, bitacora) se ejecuta de verdad sin red.
"""

import logging
import random
import time

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from domain.ai_assistant.errors import LlmNotConfigured, LlmProviderError, LlmRateLimited, LlmTimeout
from domain.ai_assistant.ports import LlmGateway, LlmResult

RETRYABLE_STATUS = (429, 503)
logger = logging.getLogger(__name__)


def _call_model(api_key, model, system_prompt, user_prompt, timeout_s, temperature):
    """Unica funcion que habla con la red."""
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=int(timeout_s * 1000)))
    return client.models.generate_content(
        model=model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            response_mime_type='application/json',
        ),
    )


class GeminiGateway(LlmGateway):

    def __init__(self, settings, sleep=time.sleep):
        """`settings`: funcion sin argumentos que devuelve un mapping (app.config)."""
        self._settings = settings
        self._sleep = sleep

    def _read_settings(self):
        config = self._settings()
        return {
            'api_key': config.get('GEMINI_API_KEY'),
            'model': config.get('GEMINI_MODEL'),
            'timeout_s': float(config.get('AI_TIMEOUT_SECONDS', 20)),
            'max_retries': int(config.get('AI_MAX_RETRIES', 2)),
            'backoff_s': float(config.get('AI_RETRY_BASE_SECONDS', 1)),
        }

    def generate(self, system_prompt, user_prompt, temperature=0.2):
        s = self._read_settings()
        if not s['api_key'] or not s['model']:
            raise LlmNotConfigured('GEMINI_API_KEY and GEMINI_MODEL must be set in backend/.env')

        attempts = 0
        started = time.perf_counter()

        def elapsed_ms():
            return round((time.perf_counter() - started) * 1000)

        while True:
            attempts += 1
            try:
                response = _call_model(s['api_key'], s['model'], system_prompt, user_prompt,
                                       s['timeout_s'], temperature)
                break
            except httpx.TimeoutException as exc:
                # No se reintenta: otro intento con el mismo timeout duplicaria la espera del usuario.
                raise LlmTimeout(f'The model did not answer within {s["timeout_s"]:g} s',
                                 attempts, elapsed_ms()) from exc
            except genai_errors.APIError as exc:
                if exc.code in RETRYABLE_STATUS and attempts <= s['max_retries']:
                    delay = s['backoff_s'] * (2 ** (attempts - 1)) + random.uniform(0, s['backoff_s'] / 2)  # retry jitter, not security  # nosec B311
                    logger.warning('Gemini %s, retry %s in %.1f s', exc.code, attempts, delay)
                    self._sleep(delay)
                    continue
                if exc.code == 429:
                    raise LlmRateLimited('The AI provider rate limit was reached', attempts, elapsed_ms()) from exc
                raise LlmProviderError(f'The AI provider answered with HTTP {exc.code}',
                                       attempts, elapsed_ms()) from exc
            except httpx.TransportError as exc:
                raise LlmProviderError(f'Could not reach the AI provider: {type(exc).__name__}',
                                       attempts, elapsed_ms()) from exc

        usage = response.usage_metadata
        return LlmResult(
            text=response.text or '',
            model=response.model_version or s['model'],
            input_tokens=(usage.prompt_token_count or 0) if usage else 0,
            output_tokens=(usage.candidates_token_count or 0) if usage else 0,
            thinking_tokens=(usage.thoughts_token_count or 0) if usage else 0,
            latency_ms=elapsed_ms(),
            attempts=attempts,
        )
