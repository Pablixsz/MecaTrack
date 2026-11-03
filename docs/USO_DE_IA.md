# Uso de IA – Guía 6 (Sesiones 11 y 12)

Trazabilidad del código generado con IA, exigida por la guía ("Documente
siempre qué generó la IA y qué cambios realizó").

- **Herramienta:** Claude Code (modelo Claude Opus 5.5, Anthropic), en la terminal, sobre este repositorio.
- **Estudiante:** Pablo Rodríguez. Revisa, aprueba cada fase y hace los ajustes manuales.
- **Regla de trabajo:** la IA propone un plan por fase, espera la aprobación, ejecuta, corre las pruebas y hace un commit por fase. No hace push sin autorización.

> Las secciones marcadas con **[COMPLETAR]** las debe escribir Pablo con su propia experiencia.

---

## Fase 0 – Diagnóstico

| Qué hizo la IA | Cómo se verificó |
|---|---|
| Leyó la guía (`docs/GUIA_LAB_TALLER_S11_S12.docx`, copiada desde `~/Descargas`), el backend, las migraciones, los tests, el CI y el generador del informe de la Guía 5 | Corrió la suite base: 31 pruebas en verde |
| Consultó el catálogo real de datos.gov.co (API de Socrata) para no proponer datasets inventados | Respuestas HTTP 200 con ids reales (`u3vn-bdcy`, `gdxc-w37w`) |

Decisiones que tomó Pablo: aprobar el plan y migrar los 9 blueprints (no solo agendamiento y pagos).

## Fase 1 – Refactor a arquitectura hexagonal

### Código generado por la IA

| Archivo(s) | Contenido |
|---|---|
| `backend/domain/**` | Entidades (dataclasses), reglas puras (`scheduling/rules.py`, `payments/rules.py`), puertos ABC y errores de dominio. `allocation.py` (motor de agendamiento) se convirtió en servicio de dominio con DI. `retrieval.py`, `prompts.py` y `answer.py` (RAG) quedaron como funciones puras. |
| `backend/application/**` | Casos de uso por contexto con dependencias por constructor: `AuthService`, `BusinessService`, `StaffService`, `BayService`, `PartService`, `ServiceCatalogService`, `VehicleService`, `AppointmentService`, `PaymentService`, `TrackingService`, `AiAssistantService`. |
| `backend/infrastructure/**` | Modelos ORM (movidos sin cambios de esquema), repositorios SQLAlchemy como adaptadores (`SqlAlchemyRepository` mapea filas a entidades), `SqlAlchemyUnitOfWork`, `SystemClock`, `WerkzeugPasswordHasher` y `GeminiGateway` (antes `services/llm_client.py`). |
| `backend/api/**` | Rutas antiguas y v1 reescritas como adaptadores delgados, `SessionUser` (Flask-Login sin acoplar el ORM) y un manejador único de errores de dominio → HTTP. |
| `backend/bootstrap.py` | Composition root único. |
| `backend/tests/test_legacy_routes.py` | 7 pruebas de caracterización de rutas que no tenían cobertura. |
| `backend/tests/test_architecture.py` | Reglas de dependencias verificadas con `ast`. |

### Cómo se verificó que no se rompió nada

1. Las 31 pruebas existentes pasan sin cambiar ninguna aserción; solo se actualizaron los imports a las rutas nuevas.
2. Las 7 pruebas nuevas de caracterización se corrieron primero contra el código **original** (worktree en el commit `7cca398`, antes `45b5a4f`; 7/7 en verde) y después contra el refactor (7/7 en verde).
3. `flask db check`: *No new upgrade operations detected*, es decir, el esquema no cambió.
4. `scripts/export_openapi.py`: `docs/openapi.json` sin diferencias.
5. Prueba de humo de la app real contra la base de desarrollo: login y 7 rutas protegidas con respuesta 200.
6. Prueba de mutación de la regla de arquitectura: se añadió `import flask` a `domain/payments/rules.py`, la prueba falló como se esperaba y luego se revirtió.

### Errores de la IA detectados durante la fase (reales)

| Error | Cómo se detectó | Corrección |
|---|---|---|
| En `ServiceCatalogService.create` quedaron 3 líneas sin sentido (`hasattr(self._business, 'get_owned_or_none')`, un método que no existe) | Revisión del propio código antes de correr las pruebas | Se eliminaron |
| `scripts/run_prompt_eval.py` usaba una variable `assistant` que no estaba definida tras cambiar los imports | Revisión de los usos con `grep` | Se pasa el servicio como parámetro de `run_case` |
| El docstring de `test_legacy_routes.py` afirmaba que las pruebas se escribieron "antes del refactor", y no era cierto | Relectura | Se cambió a lo que realmente ocurrió: se escribieron durante el refactor y se validaron contra el código original |

### Decisiones de diseño que Pablo debe revisar y poder defender

- **Mensajes de error en la capa de aplicación:** los casos de uso conservan los textos en español de las rutas antiguas y en inglés de `/api/v1`, para no cambiar el contrato del frontend. La alternativa (traducir por `code` en la api) se descartó por alcance.
- **`TrackingService.record_step`** valida todos los repuestos *antes* de escribir. El código original creaba el registro y hacía `rollback` si fallaba. El resultado HTTP es el mismo y el stock no cambia en los intentos fallidos (lo prueba `test_tracking_records_steps_and_discounts_stock`).
- **`api` puede importar `domain`** (por ejemplo, las constantes de prompts para el esquema Marshmallow, o `Actor`), pero no `infrastructure`.

**[COMPLETAR]** Qué revisó Pablo personalmente y qué cambiaría.

---

## Fase 2 – Inyección de dependencias y pruebas unitarias con mocks

La guía pide "Mockito"; el stack confirmado es Python, así que se usó `unittest.mock` (librería estándar).

### Código generado por la IA

| Archivo | Qué prueba |
|---|---|
| `tests/unit/test_appointment_service.py` | `AppointmentService` con sus 6 dependencias simuladas: asignación, 2 pagos 30/70, un solo commit, nada escrito si no hay disponibilidad, reglas de cancelación y permisos del mecánico |
| `tests/unit/test_payment_service.py` | `PaymentService` con `Clock` simulado: el depósito confirma la cita, el saldo no; pagos inválidos no escriben |
| `tests/unit/test_resource_allocator.py` | Servicio de dominio con puertos simulados: primera bahía y primer mecánico libres; no consulta mecánicos si no hay bahía |
| `tests/unit/test_tracking_service.py` | El descuento de stock es todo o nada |
| `tests/unit/test_ai_assistant_service.py` | El LLM simulado como puerto: precios del catálogo, ids inventados descartados, fallos registrados, cuota con reloj inyectado |
| `tests/unit/test_domain_rules.py` | Reglas puras, sin mocks |
| `tests/conftest.py`, `tests/integration/conftest.py` | Separación: las fixtures que truncan PostgreSQL solo aplican a `integration/` |

### Verificación

- 43 pruebas unitarias en 0.3 s. También pasan con una `DATABASE_URL` inválida, lo que demuestra que no tocan la base.
- **Prueba de mutación:** con `DEPOSIT_PERCENTAGE = 0.4` fallan 3 pruebas, justo las del 30/70. Luego se revirtió.
- La suite completa da 81 en verde (38 de integración + 43 unitarias).

### Decisión técnica a defender

Se usó `create_autospec(Puerto, instance=True)` en lugar de `Mock()`. Un `Mock()` acepta cualquier método y firma, y no detectaría que el servicio usa algo que el puerto no declara. Lo demuestra `test_autospec_mocks_enforce_the_port_contract`.

**[COMPLETAR]** Experiencia personal de Pablo con las pruebas unitarias.

---

## Fase 3 – APIs colombianas, circuit breaker y retry

### Verificación previa de las APIs (llamadas reales del 2026-10-24, antes de escribir código)

| Fuente | Endpoint | Resultado real |
|---|---|---|
| RUNT, parque automotor (MinTransporte) | `datos.gov.co/resource/u3vn-bdcy.json` | 191 922 filas, 22 655 040 vehículos, publicación de octubre de 2026; 28 007 filas agregadas por departamento, clase y año |
| DIVIPOLA (DANE) | `datos.gov.co/resource/gdxc-w37w.json` | 1 122 municipios, 33 departamentos |
| Población CNPV 2018 (DANE) | `geoportal.dane.gov.co/.../Serv_Mpios_DistribucionPoblacionTotalCen_2018/MapServer/4/query` | 1 122 municipios, 44 164 417 personas censadas |
| Descartadas | precios de combustible `x6id-4v3g` (2018), IPC del geoportal (2012–2013) | Desactualizadas |

**Primer error de la IA en esta fase:** la primera consulta SoQL codificó toda la cadena (incluidos los `&`) en un solo parámetro y Socrata respondió `400 query.compiler.malformed`. Se corrigió pasando cada parámetro por separado. El error se detectó por la respuesta HTTP real.

**Hallazgo de datos:** en el cruce RUNT ↔ DIVIPOLA, "BOGOTA D.C." no coincide con "BOGOTA, D.C." y San Andrés aparece truncado en RUNT. Se resolverá normalizando a solo letras y uniendo por prefijo (Fase 4).

### Código generado por la IA

| Archivo | Contenido |
|---|---|
| `infrastructure/resilience/circuit_breaker.py` | Breaker de 3 estados, umbral de fallos, timeout de recuperación, una sola prueba en HALF_OPEN, historial de transiciones, reloj inyectable y lock entre hilos |
| `infrastructure/resilience/retry.py` | `RetryPolicy` + `retry_call`: backoff exponencial con *equal jitter*, tope `max_delay` y lista de excepciones reintentables |
| `infrastructure/resilience/http_client.py` | httpx con retry por fuera y breaker por dentro; clasifica los errores en transitorios (timeout, conexión, 429, 5xx) y permanentes (otros 4xx) |
| `infrastructure/market_data/clients.py` | Adaptadores Socrata (paginación `$limit/$offset`) y ArcGIS (paginación `resultOffset` y errores dentro de un HTTP 200) |
| `domain/market_data/`, `application/market_data/` | Puertos y caso de uso `MarketDataService` (una fuente caída no detiene a las demás) |
| `scripts/demo_resilience.py` | **Demostración controlada** con red real |
| `tests/fixtures/market/` | Respuestas **reales** recortadas de las 3 fuentes, para pruebas sin red |

### Verificación

- 23 pruebas nuevas (breaker, retry, cliente HTTP con `httpx.MockTransport`, fuentes y caso de uso): 104 en verde en total.
- **Mutación:** con `>` en lugar de `>=` en el umbral del breaker fallan 4 pruebas. Luego se revirtió.
- Adaptadores contra las APIs reales: RUNT 28 007 filas (1,1 s), DIVIPOLA 1 122 (0,27 s), DANE 1 122 (1,1 s).
- `demo_resilience.py` con red real: separación entre intentos de 0,317 / 0,607 / 1,101 / 3,416 s; transiciones CLOSED→OPEN→HALF_OPEN→OPEN→HALF_OPEN→CLOSED; rechazo en ~35 µs con el circuito abierto.

### Decisiones a defender

- **Un breaker por host** (datos.gov.co y geoportal.dane.gov.co): la caída de uno no bloquea al otro.
- **Retry por fuera y breaker por dentro**, y `CircuitOpenError` no se reintenta: no tiene sentido esperar un backoff si ya se sabe que la dependencia está caída.
- **Un 4xx no abre el circuito**: indica un error de la petición, no de la salud de la dependencia.
- **RUNT se agrega en el servidor** (SoQL `group by`): 3 MB en vez de ~27 MB, porque el detalle por municipio no se usa.

**[COMPLETAR]** Opinión de Pablo sobre las decisiones anteriores.

---

## Fase 4 – DuckDB, endpoints y visualización

### Código generado por la IA

| Archivo | Contenido |
|---|---|
| `infrastructure/analytics/queries.py` | 3 consultas SQL: antigüedad del parque por clase (estadísticas **ponderadas**: media, desviación, P25, mediana, P75, P90, mín./máx.), motorización por departamento (RUNT ⋈ DIVIPOLA ⋈ CNPV con resumen entre departamentos) y distribución por rangos |
| `infrastructure/analytics/duckdb_analytics.py` | Adaptador `MarketAnalytics`: `read_json` + `unnest` sobre los snapshots, una conexión en memoria por consulta |
| `api/v1/market.py`, `api/v1/schemas/market_schema.py` | 5 endpoints documentados en OpenAPI (owner/admin) |
| `frontend/pages/mercado.html`, `js/mercado.js`, `js/graficos.js` | Vista vanilla: estado de los breakers, tablas, KPIs y 2 gráficos en Canvas (barras horizontales con referencia nacional y apiladas al 100 %) con tooltip |

**Dependencia nueva:** `duckdb==1.5.6`. Se descartó la 2.0.0 porque era una versión mayor publicada 3 días antes (2026-10-21); la 1.5.6 es del 2026-09-28 y tiene wheels para Python 3.12 (CI) y 3.14 (local).

> **Actualización (2026-11-02):** se adoptó `duckdb==2.0.0` (PR #1 de Dependabot). Las tres consultas del panel Mercado dieron resultados idénticos con 1.5.6 y 2.0.0 sobre los snapshots locales. Las salidas de `docs/evidencia/salidas/11_duckdb_q1.txt` y `12_duckdb_q2.txt` se generaron con 1.5.6.

### Errores de la IA detectados en esta fase

| Error | Cómo se detectó | Corrección |
|---|---|---|
| `CREATE VIEW ... read_json(?)` con parámetro preparado: DuckDB lo rechaza (`Unexpected prepared parameter`) | Ejecución real | Literal SQL escapado; el path sale de la configuración |
| `LEFT JOIN` con `NOT EXISTS` correlacionado: `Cannot perform non-inner join on subquery` | Ejecución real | Se resuelve primero la clave DIVIPOLA (exacta o por prefijo) y luego un join simple |
| Una línea absurda en `api/v1/market.py` (`... if False else decorate`) | Revisión del código | Eliminada |
| Código del tooltip duplicado en `graficos.js` | Revisión del código | Unificado en `canvas._buscar` |
| Capturas de Playwright: tabla de fuentes desbordada, columna cortada, valores tapados por la línea nacional y el "100 %" del eje recortado | Revisión visual de la captura | CSS de tablas compactas, halo en las etiquetas, margen derecho |
| La prueba de interacción falló dos veces, por errores **de la prueba** y no de la app: el canvas estaba fuera del viewport y hubo una carrera al leer la tabla | Depuración con `page.evaluate` | `scroll_into_view_if_needed()` y esperar a la insignia |

### Verificación con datos reales (snapshot del 2026-10-24)

- **Q1:** 22 054 289 vehículos, 9 clases; mediana de 9 años en motos y de 16 en automóviles; 8 864 excluidos por calidad (registro < 1950). 89,5 ms.
- **Q2:** 33 departamentos (Vaupés sin registros en RUNT); 499,4 vehículos por 1 000 hab. a nivel nacional; media 514,8, mediana 446,5, desviación 343,9. ~100 ms.
- **Validación cruzada:** las estadísticas ponderadas coinciden **exactamente** con `quantile_disc`/`stddev_pop` de DuckDB sobre los datos expandidos a una fila por vehículo (22 M filas, 1,1 s), en las 9 clases. El total de la Q2 es igual al de la Q1: el cruce no pierde ni duplica vehículos.
- **Interpretación (advertencia en la UI):** RUNT ubica el vehículo donde se matriculó. Por eso Guaviare (2 021, 99 % motos) y Cundinamarca (1 000) superan a Bogotá (387).
- **Pruebas:** 11 nuevas (adaptador DuckDB con fixtures reales, regla del cruce por prefijo y endpoints con red simulada, incluido un corte de datos.gov.co que abre su breaker mientras el del DANE sigue CLOSED). Total: 115 en verde.
- **Gráficos:** colores verificados con el validador de paletas (rampa ordinal de un solo tono, luminosidad monótona, paso más claro ≥ 2:1). Se comprobaron en Playwright el tooltip, el botón de actualizar (descarga real: 1 632 / 274 / 880 ms) y la vista móvil de 390 px sin scroll horizontal.

**[COMPLETAR]** Qué conclusiones saca Pablo para el negocio del taller.

---

## Fase 5 – ADR en inglés

- **Generado por la IA:** `docs/adr/0001-hexagonal-architecture.md` (plantilla de Nygard): contexto, decisión, 7 bounded contexts con su tipo de subdominio y puertos, mapa de contextos (cliente/proveedor, conformista, capa anticorrupción), DI, resiliencia, 5 alternativas descartadas y consecuencias positivas y negativas.
- **Verificación:** todas las cifras salen de ejecuciones reales (18 puertos ABC, 73 pruebas unitarias en 1,12 s, 42 de integración en 14,7 s, ~60 líneas de cableado). Las 4 URLs de las referencias respondieron HTTP 200 el 2026-10-24; los libros (Evans, 2003; Nygard, 2018) son ediciones publicadas.
- **Error de la IA detectado:** el borrador decía "11-service graph", pero tras la Fase 3 el contenedor tiene 12 servicios. Se detectó contando los campos de `Container` y se corrigió.
- **A revisar por Pablo:** la clasificación de subdominios (core/supporting/generic) es una decisión de diseño que debe poder defender. **[COMPLETAR]** Acuerdo o cambios.

---

## Fase 6 – CI en GitHub Actions

- El workflow existente (`.github/workflows/mecatrack-tests.yml`: PostgreSQL 16, Python 3.12, pytest y verificación de `openapi.json`) **no necesitó cambios**. Ya ejecuta las dos carpetas de pruebas, porque `testpaths = tests`, y `duckdb==1.5.6` entró por `requirements.txt`.
- Antes del push (autorizado por Pablo) se escanearon los 16 commits pendientes en busca de secretos (claves de Google, tokens de GitHub, URLs con contraseña): no había ninguno.
- No se incluyó el borrado sin commit de `Taller1/` y `Actividad_2/`.
- Resultado real: run `40154151261` del commit `4eb6286` (hoy `9ba8a46`, ver «Reescritura del historial») → **completed / success**.
  https://github.com/pablo-rodriguez091004/TallerDeProgramaci-n/actions/runs/40154151261
- Suite local antes del push: 115 pruebas en verde (73 unitarias + 42 de integración).

---

## Fase 7 – Evidencia (capturas)

- **Generado por la IA:** `scripts/generar_evidencia.sh` (un solo paso), `scripts/evidencia/{render,capturar,consultar_apis,consultas_duckdb}.py` y 18 capturas en `docs/evidencia/` (índice en `docs/evidencia/README.md`).
- **Instalado:** nada nuevo en el sistema. Playwright 1.64.0 y Chromium ya estaban de la Guía 5; Pygments 2.21.0 ya venía con pytest y se fijó en `scripts/requirements-evidence.txt`. `tree` ya estaba en Fedora. **No se instaló `gh`**: el repositorio es público, así que el CI se consultó con la API REST de GitHub y se capturó con Playwright.
- **Honestidad:** las imágenes de terminal se generan a partir de la salida real de cada comando (guardada en `docs/evidencia/salidas/`). Los recortes están declarados en la imagen ("JSON recortado a 3 registros", "se omite la Parte A…"). Las capturas 08, 10 y 14 son **demostraciones controladas** (host `.invalid`), y así lo dicen.
- **Errores detectados al revisar cada imagen (y corregidos):**
  1. Las ligaduras de la fuente convertían `->`, `!=` y `===` en flechas y símbolos, lo que en una evidencia de código es engañoso. Se desactivaron.
  2. pytest imprimía a 150 columnas y las líneas se partían. Ahora usa `COLUMNS=118`.
  3. `tree` producía una imagen de 5 832 px. Se dividió en dos comandos reales lado a lado.
  4. Los IDs de una prueba parametrizada salían escapados (`Veh\xedculo`). Se añadieron `ids=` legibles a la prueba.
  5. La página de Mercado y el ADR completos eran demasiado altos para el Word. Se dividieron por secciones.
  6. La barra de navegación *sticky* tapaba la tabla en la 13b. Se fija como estática solo durante esa captura.
- **Cambio de configuración para la demo:** `MARKET_SOCRATA_BASE_URL` (por defecto la URL real de datos.gov.co). Solo el script de evidencia la cambia.
- **Aviso:** la captura del CI corresponde al último run en verde (`4eb6286`, hoy `9ba8a46`). Los commits posteriores a la Fase 5 solo cambian documentación, scripts y una prueba; el CI se vuelve a ejecutar con el próximo push que toque `backend/`.

---

## Fase 8 – Informe Word (APA 7)

- **Generado por la IA:** `informe/build_informe_guia6.js` → `informe/Informe_Guia6_MecaTrack.docx`. Los helpers de formato se extrajeron a `informe/apa.js` con el **mismo estilo** que la Guía 5 (Times New Roman 12, carta, márgenes de 1", doble espacio, rótulos APA de tablas y figuras, notas a 10 pt). El generador de la Guía 5 no se tocó.
- **Portada:** sigue la versión final que Pablo ajustó a mano en la Guía 5 (sin línea de docente), con nombre y código en `[COMPLETAR]`.
- **Datos:** el script **lee** todas las cifras de `docs/evidencia/salidas/` (pytest, APIs, demo de resiliencia, analítica DuckDB, run del CI, commits) y falla si los conteos no cuadran. No hay números escritos a mano.
- **Referencias:** las 21 con URL se comprobaron con HTTP 200 el 2026-10-24; el RFC 2606 se cita por su DOI.
- **Revisión visual:** se convirtió a PDF con LibreOffice y se revisaron las 41 páginas. Se encontró y corrigió una nota interna del script de capturas que se había colado en la sección de CI; ahora el informe explica con datos qué commit cubre el CI.
- **[COMPLETAR] en el informe:** nombre y código, conclusión de negocio, dificultad personal, experiencia con Copilot, enlaces (repositorio, CI y YouTube) y la declaración de uso de IA.

## Fase 9 – Video en inglés

- **Generado por la IA:** `docs/video_script_EN.md` (320 palabras habladas, ≈ 2 min 17 s a 140 ppm; incluye un glosario en inglés como recurso previo) y `scripts/demo.sh` (modo normal, `--breaker-abierto` para la demostración controlada en la UI y `--ciclo` para el ciclo completo en terminal).
- **Verificado:** `demo.sh` levanta backend y frontend (HTTP 200 en ambos) y libera los puertos al detenerse.
- **Pendiente de Pablo:** grabar el video, decir su nombre y, si usó Copilot, reemplazar el ejemplo de la sección 4 por el suyo.

## Reescritura del historial (2026-10-24, pedida por Pablo)

Pablo pidió eliminar de forma definitiva `Taller1/` y `Actividad_2/` y que en su carpeta de trabajo quedara solo `PROYECTO_FINAL/`. Se aplicó así:

1. **Respaldo** completo con `git bundle` (verificado, todas las ramas) en `~/Escritorio/TallerDeProgramacion-respaldo-git-2026-10-24.bundle`.
2. Con `git filter-repo` 2.47.0 (instalado en un entorno virtual temporal, no en el sistema), en un clon aparte, sobre `master` y `mecatrack-final`: se conservó solo `PROYECTO_FINAL/` (que pasó a ser la **raíz del repositorio**) y el workflow. En el historial ya no queda ningún archivo de `Taller1/` ni de `Actividad_2/`. La rama `feature/add-dip-and-tests-pr` no se tocó.
3. **Verificación:** el contenido final es idéntico byte a byte (286 archivos) al `PROYECTO_FINAL/` anterior más el workflow.
4. El workflow, el README, el ADR y los scripts se actualizaron a las rutas nuevas (`backend/**` en lugar de `PROYECTO_FINAL/backend/**`).

Como cambió el identificador de cada commit, esta es la equivalencia de los citados en este documento:

| Antes | Ahora | Commit |
|---|---|---|
| `45b5a4f` | `7cca398` | Guía 5: ajustes manuales (base de la Guía 6) |
| `0a2c6f3` | `66a0977` | Fase 1 |
| `4c69d37` | `63c197c` | Fase 2 |
| `4433138` | `103ed7e` | Fase 3 |
| `04843b5` | `e53c462` | Fase 4 |
| `4eb6286` | `9ba8a46` | Fase 5 (CI run 40154151261) |
| `a3a2b46` | `fc2d2a7` | Fase 6 |
| `f688fba` | `f6226f6` | Fase 7 |
| `caf881c` | `c7c6027` | Fase 8 |
| `1efeec5` | `7804214` | Fase 9 (CI run 40155508580) |
| `afcdb84` | `b7f2ebc` | Evidencia final |
| `ff35401` | — | Borrado de las carpetas: quedó vacío y se descartó |

Los runs de GitHub Actions anteriores quedan registrados sobre los commits viejos. La evidencia y el informe se regeneraron después con el CI de los commits nuevos.

**CI después de la reescritura.** El *force push* no disparó el workflow, así que no había un run sobre los commits nuevos. En lugar de un commit vacío se hizo un cambio útil: las actions se actualizaron a versiones con Node 24 (`checkout@v7.0.1`, `setup-python@v7.0.0`, `upload-artifact@v7.0.2`), con versiones fijas verificadas y sin usar la `setup-python` v7.1.0, publicada 2 días antes. Eso eliminó el aviso de deprecación de Node.js 20. Resultado: run `40156647221` del commit `7c3e54a` → **success**. La evidencia y el informe se regeneraron con ese run.

## Extra – Rol administrador y recepción (2026-10-25, pedido por Pablo)

- **Necesidad (Pablo):** una persona que administre el negocio, agende citas de clientes nuevos y esté pendiente del inventario.
- **Generado por la IA:**
  - Usuario de prueba `admin@tallermecanico.com` creado con `scripts/crear_admin.py`, que no duplica si ya existe.
  - Endpoints `GET` y `POST /businesses/clients`.
  - Registro de vehículos y agendamiento con `client_user_id` para `owner` y `admin`.
  - Pestaña **Recepción** en el Panel del taller, con registro del depósito.
  - 13 pruebas nuevas (unitarias con mocks y una de integración del flujo completo).
- **Regla de negocio:** el cliente sigue sin poder actuar a nombre de otro (403) y el mecánico no tiene acceso a recepción. Crear o desactivar mecánicos sigue siendo exclusivo del dueño.
- **Verificación:** 128 pruebas en verde. Prueba de punta a punta con Playwright en la app real: cliente nuevo, vehículo, cita, depósito y cita **Confirmada** que el cliente ve en su historial. Los datos de prueba se borraron de la base de desarrollo. CI en verde en `master` y `mecatrack-final`.
- **Errores de la IA en esta parte:**
  - La prueba de punta a punta falló una vez porque esperaba el texto "Bahía", que la propia IA había quitado de la interfaz. Se corrigió la prueba.
  - Un `pkill` cuyo patrón aparecía en la propia línea de comando cerró la terminal de la IA; desde entonces los procesos se detienen por PID.
