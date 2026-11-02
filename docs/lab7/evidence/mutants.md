# Mutation testing con mutmut

Herramienta: mutmut 3.8.1. Alcance: `domain/scheduling`, `domain/payments`, `application/scheduling` y `application/payments` (294 mutantes al inicio y 320 al final), con las pruebas de `tests/unit`, sin base de datos.

| Momento | Killed | Survived | Sin pruebas | Total | Score |
|---|---|---|---|---|---|
| Inicial | 184 | 93 | 17 | 294 | 62.6 % |
| Tras las pruebas de la Fase 2 | 289 | 5 | 0 | 294 | 98.3 % |
| Final, con la logica nueva de la Fase 5 | 315 | 5 | 0 | 320 | 98.4 % |

El score mide solo ese alcance, no todo el backend. `test_architecture.py` se excluye de la corrida porque lee el codigo fuente, y el codigo instrumentado importa `mutmut`; sigue corriendo en el CI normal.

## Mutantes por funcion

Sobrevivientes / sin pruebas, antes y despues.

| Modulo | Funcion | Antes | Despues | Pruebas anadidas |
|---|---|---|---|---|
| `domain.scheduling.allocation` | `find_available_bay` | 4 / 0 | 0 / 0 | test_bay_lookup_forwards_the_slot_and_the_excluded_appointment |
| `domain.scheduling.allocation` | `find_available_mechanic` | 4 / 0 | 0 / 0 | test_mechanic_lookup_forwards_the_slot_and_the_excluded_appointment |
| `domain.scheduling.allocation` | `find_bay_and_mechanic` | 12 / 0 | 0 / 0 | test_bay_and_mechanic_search_forwards_every_argument |
| `domain.scheduling.rules` | `ensure_participant` | 2 / 0 | 0 / 0 | test_ensure_participant_raises_with_the_given_message |
| `application.scheduling.services` | `book` | 14 / 0 | 4 / 0 | test_book_looks_up_the_requested_vehicle_and_service, test_book_defaults_to_cash_and_pending_payments, test_book_stores_vehicle_service_and_start |
| `application.scheduling.services` | `_client_for` | 5 / 0 | 1 / 0 | test_booking_for_someone_else_explains_why_it_is_denied, test_a_client_may_name_himself_when_booking |
| `application.scheduling.services` | `list_for` | 0 / 1 | 0 / 0 | test_list_for_delegates_with_the_actor |
| `application.scheduling.services` | `get` | 0 / 16 | 0 / 0 | test_get_returns_the_view_for_a_participant, test_get_unknown_appointment_is_not_found, test_get_denies_someone_else |
| `application.scheduling.services` | `change_status` | 10 / 0 | 0 / 0 | test_change_status_saves_the_new_status_and_commits, test_change_status_rejects_unknown_status |
| `application.scheduling.services` | `cancel` | 9 / 0 | 0 / 0 | test_cancel_loads_the_requested_appointment, test_cancel_errors_explain_why |
| `application.scheduling.services` | `_get` | 5 / 0 | 0 / 0 | test_change_status_of_unknown_appointment_is_not_found |
| `application.payments.services` | `list_for_appointment` | 10 / 0 | 0 / 0 | test_list_reads_the_payments_of_the_requested_appointment, test_list_of_unknown_appointment_is_not_found, test_list_denial_explains_why |
| `application.payments.services` | `pay` | 18 / 0 | 0 / 0 | test_pay_loads_the_payment_and_its_appointment, test_pay_errors_explain_why, test_unknown_payment_message |

## Sobrevivientes finales

| Mutante | Cambio | Motivo |
|---|---|---|
| `status='pending'` de la cita | Quita `status='pending'` de la cita | Equivalente: `pending` es el valor por defecto de la entidad |
| `status='pending'` del pago | Quita `status='pending'` del pago | Equivalente: mismo motivo |
| Mensajes de `book` y `_client_for` | Altera el texto del mensaje con `XX` | Las pruebas comprueban el mensaje por coincidencia parcial; no cambia el comportamiento |

## Como ejecutarlo

    cd backend
    pip install -r requirements-dev.txt
    mutmut run
    mutmut export-cicd-stats
    python ../scripts/mutation_score.py

mutmut usa `fork` para aislar los mutantes, por lo que no corre en Windows nativo. En Windows, usar WSL o dejar que lo ejecute el job de GitHub Actions.
