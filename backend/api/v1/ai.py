"""
POST /api/v1/ai/suggest-service: el cliente describe un sintoma y el LLM
sugiere servicios del catalogo (RAG). La logica vive en
application/ai_assistant/services.py (AiAssistantService);
aqui solo se valida, se aplica el limite por usuario y se mapean errores a HTTP.
"""

from flask import current_app
from flask.views import MethodView
from flask_jwt_extended import current_user
from flask_smorest import Blueprint

from api.auth import role_required
from api.deps import container
from api.errors import ApiError
from api.v1.schemas.ai_schema import SuggestServiceRequestSchema, SuggestServiceResponseSchema
from api.v1.schemas.error_schema import UNAUTHORIZED_EXAMPLE, ApiErrorSchema, error_example
from domain.ai_assistant import errors as ai_errors
from domain.shared.actor import ROLES

blp = Blueprint('AI', __name__, description='LLM-powered assistant that suggests catalog services (RAG).')

# Excepcion del cliente LLM -> (HTTP, code, message publico)
LLM_ERRORS = {
    ai_errors.LlmNotConfigured: (503, 'ai_not_configured', 'The AI assistant is not configured on this server'),
    ai_errors.LlmTimeout: (504, 'llm_timeout', 'The AI provider did not answer in time, please try again'),
    ai_errors.LlmRateLimited: (429, 'llm_rate_limited', 'The AI provider is rate limiting requests, try again later'),
    ai_errors.LlmProviderError: (502, 'llm_provider_error', 'The AI provider failed to process the request'),
}

REQUEST_EXAMPLE = {'description': 'El carro vibra cuando freno en bajada', 'technique': 'few_shot'}


def _error(status, description, example):
    return blp.alt_response(status, schema=ApiErrorSchema, description=description, example=example)


@blp.route('/suggest-service')
class SuggestService(MethodView):

    @role_required(*ROLES)
    @blp.arguments(SuggestServiceRequestSchema, example=REQUEST_EXAMPLE)
    @blp.response(200, SuggestServiceResponseSchema, description='Suggested services with price and duration.',
                  example={
                      'ai_call_id': 17, 'technique': 'few_shot', 'model': 'gemini-3.5-flash-lite',
                      'suggestions': [{'service_id': 4, 'service_name': 'Rectificación de discos de freno',
                                       'base_price': 220000, 'estimated_duration_minutes': 120,
                                       'confidence': 'high',
                                       'reason': 'La vibracion al frenar suele indicar discos alabeados.'}],
                      'notes': 'Los frenos son un tema de seguridad; agenda pronto.', 'reasoning': None,
                      'discarded_service_ids': [],
                      'retrieval': {'strategy': 'keyword', 'fallback_full_catalog': False,
                                    'candidate_service_ids': [4, 3, 2]},
                      'usage': {'input_tokens': 412, 'output_tokens': 96, 'thinking_tokens': 0,
                                'latency_ms': 1180, 'attempts': 1}})
    @_error(401, 'Missing or invalid token. Log in with POST /api/auth/login first.', UNAUTHORIZED_EXAMPLE)
    @_error(422, 'Invalid body, e.g. a description that is too short or an unknown technique.', error_example(
        'validation_error', 'The request body is invalid',
        {'technique': ['Must be one of: zero_shot, few_shot, cot.']}))
    @_error(429, 'Too many requests: the per-user hourly limit (`user_quota_exceeded`, with a Retry-After '
                 'header) or the provider rate limit after the retries (`llm_rate_limited`).', error_example(
        'user_quota_exceeded', 'You reached the limit of 20 AI requests per hour', {'retry_after_seconds': 1800}))
    @_error(502, 'The provider failed (`llm_provider_error`) or returned an answer that is not the expected '
                 'JSON (`invalid_llm_response`).', error_example(
        'llm_provider_error', 'The AI provider failed to process the request', {'ai_call_id': 18, 'attempts': 1}))
    @_error(503, 'The server has no GEMINI_API_KEY / GEMINI_MODEL configured.', error_example(
        'ai_not_configured', 'The AI assistant is not configured on this server', None))
    @_error(504, 'The provider did not answer before AI_TIMEOUT_SECONDS.', error_example(
        'llm_timeout', 'The AI provider did not answer in time, please try again', {'ai_call_id': 19, 'attempts': 1}))
    @blp.doc(security=[{'bearerAuth': []}])
    def post(self, data):
        """Suggest services for a symptom

        The customer describes a vehicle problem in free text and the
        assistant suggests up to 3 services of the workshop catalog.
        Retrieval-augmented generation: the API first retrieves the relevant
        catalog services by keyword, injects them into the prompt and asks the
        model to choose ONLY among them. Prices and durations come from the
        database, never from the model. Every call is stored in `ai_calls`.
        Any logged-in user can call it, up to `AI_MAX_CALLS_PER_HOUR` times per hour.
        """
        assistant = container().ai_assistant
        limit = int(current_app.config.get('AI_MAX_CALLS_PER_HOUR', 20))
        try:
            assistant.check_user_quota(current_user.user_id, limit)
        except ai_errors.UserQuotaExceeded as exc:
            raise ApiError(429, 'user_quota_exceeded', f'You reached the limit of {limit} AI requests per hour',
                           {'retry_after_seconds': exc.retry_after_s},
                           headers={'Retry-After': str(exc.retry_after_s)}) from exc

        try:
            return assistant.suggest_services(data['description'], data['technique'], user_id=current_user.user_id)
        except ai_errors.LlmError as exc:
            status, code, message = LLM_ERRORS[type(exc)]
            raise ApiError(status, code, message,
                           {'ai_call_id': getattr(exc, 'ai_call_id', None), 'attempts': exc.attempts}) from exc
        except ai_errors.InvalidModelResponse as exc:
            raise ApiError(502, 'invalid_llm_response', 'The AI provider returned an unexpected answer',
                           {'ai_call_id': getattr(exc, 'ai_call_id', None), 'reason': str(exc)}) from exc
