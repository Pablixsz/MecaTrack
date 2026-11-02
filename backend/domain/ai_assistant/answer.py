"""Validacion de la respuesta JSON del modelo (defensa contra alucinaciones)."""

import json

from domain.ai_assistant import prompts
from domain.ai_assistant.errors import InvalidModelResponse

CONFIDENCE_LEVELS = ('high', 'medium', 'low')


def _strip_code_fence(text):
    """Quita las cercas ``` del modelo sin regex: su texto no es confiable y no debe poder ralentizar el parseo."""
    cleaned = text.strip()
    if cleaned.startswith('```'):
        cleaned = cleaned[3:].removeprefix('json')
    return cleaned.removesuffix('```').strip()


def parse_model_answer(text, allowed_ids):
    """
    Devuelve (sugerencias, notes, reasoning, descartados). Los service_id que
    no estaban en el contexto se descartan: el modelo no puede inventar servicios.
    """
    cleaned = _strip_code_fence(text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise InvalidModelResponse(f'The model did not return valid JSON: {exc.msg}') from exc
    if not isinstance(data, dict) or not isinstance(data.get('suggestions'), list):
        raise InvalidModelResponse('The model JSON has no "suggestions" list')

    suggestions, discarded, seen = [], [], set()
    for item in data['suggestions']:
        if not isinstance(item, dict):
            continue
        service_id = item.get('service_id')
        if not isinstance(service_id, int) or service_id not in allowed_ids:
            discarded.append(service_id)
            continue
        if service_id in seen:
            continue
        seen.add(service_id)
        confidence = item.get('confidence') if item.get('confidence') in CONFIDENCE_LEVELS else 'low'
        suggestions.append({'service_id': service_id, 'confidence': confidence,
                            'reason': str(item.get('reason') or '').strip()})

    notes = str(data.get('notes') or '').strip()
    reasoning = data.get('reasoning')
    return suggestions[:prompts.MAX_SUGGESTIONS], notes, reasoning, discarded
