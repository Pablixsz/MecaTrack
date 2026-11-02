"""AiAssistantService con el LLM (puerto LlmGateway) y la bitacora simulados."""

from datetime import timedelta
from unittest.mock import create_autospec

import pytest

from application.ai_assistant.services import AiAssistantService
from domain.ai_assistant.answer import parse_model_answer
from domain.ai_assistant.errors import LlmTimeout, UserQuotaExceeded
from domain.ai_assistant.ports import AiCallLog, LlmGateway, LlmResult
from domain.catalog.ports import ServiceRepository
from domain.shared.ports import Clock
from tests.unit.factories import make_service


@pytest.fixture
def deps(fixed_now):
    services = create_autospec(ServiceRepository, instance=True)
    services.list_active.return_value = [
        make_service(service_id=2, service_name='Cambio de pastillas de freno', base_price=180000),
        make_service(service_id=3, service_name='Revision de bateria', base_price=100000),
    ]
    clock = create_autospec(Clock, instance=True)
    clock.now.return_value = fixed_now
    call_log = create_autospec(AiCallLog, instance=True)
    call_log.record.return_value = 41
    return {'services': services, 'llm': create_autospec(LlmGateway, instance=True), 'call_log': call_log,
            'clock': clock}


def test_prices_come_from_the_catalog_and_invented_ids_are_discarded(deps):
    deps['llm'].generate.return_value = LlmResult(
        text='{"suggestions": [{"service_id": 2, "confidence": "high", "reason": "chilla"},'
             ' {"service_id": 77, "confidence": "high", "reason": "inventado"}]}',
        model='fake', input_tokens=10, output_tokens=5, thinking_tokens=0, latency_ms=3, attempts=1)

    result = AiAssistantService(**deps).suggest_services('Los frenos chillan al frenar', 'zero_shot', user_id=3)

    assert [(s['service_id'], s['base_price']) for s in result['suggestions']] == [(2, 180000)]
    assert result['discarded_service_ids'] == [77] and result['ai_call_id'] == 41
    assert deps['call_log'].record.call_args.kwargs['status'] == 'success'


def test_llm_failure_is_logged_and_re_raised(deps):
    deps['llm'].generate.side_effect = LlmTimeout('slow', attempts=1, latency_ms=20000)

    with pytest.raises(LlmTimeout) as error:
        AiAssistantService(**deps).suggest_services('Los frenos chillan al frenar', user_id=3)

    assert error.value.ai_call_id == 41
    assert deps['call_log'].record.call_args.kwargs['status'] == 'timeout'


def test_quota_uses_the_injected_clock(deps, fixed_now):
    deps['call_log'].api_calls_since.return_value = (2, fixed_now - timedelta(minutes=50))
    with pytest.raises(UserQuotaExceeded) as error:
        AiAssistantService(**deps).check_user_quota(3, limit=2)
    assert error.value.retry_after_s == 600  # la mas antigua sale de la ventana en 10 min
    deps['call_log'].api_calls_since.assert_called_once_with(3, fixed_now - timedelta(hours=1))
    deps['llm'].generate.assert_not_called()


# --- Regresion SonarCloud S5850: el limpiador quita las dos cercas de codigo ---

@pytest.mark.parametrize('text', [
    '{"suggestions": []}',
    '```json\n{"suggestions": []}\n```',
    '```\n{"suggestions": []}\n```',
])
def test_parse_model_answer_strips_markdown_fences(text):
    assert parse_model_answer(text, set())[0] == []
