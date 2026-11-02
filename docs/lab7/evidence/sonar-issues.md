# Issues de SonarCloud (Bug y Vulnerability)

Primer analisis (automatico) de `Pablixsz_MecaTrack`: 32 bugs y 15 vulnerabilidades. Figuras 01a y 01b.

| Issue | Severidad | Causa | Tratamiento | Test / verificacion |
|---|---|---|---|---|
| `pythonsecurity:S5131` en `api/v1/services.py:161` y `api/v1/ai.py:90` | BLOCKER | Sonar ve datos del usuario devueltos en la respuesta. Se serializan como JSON, por lo que no hay HTML reflejado directo | Se anade `X-Content-Type-Options: nosniff` a todas las respuestas para impedir que el navegador interprete el JSON como HTML | `test_user_input_is_echoed_only_as_non_sniffable_json`: comprobado que falla sin el arreglo |
| `python:S4502` en `app.py:17` | CRITICAL | API con sesion por cookie y sin proteccion CSRF: riesgo real | Abierto: se resuelve en la Fase 4 al pasar a JWT en cabecera | Pendiente de la Fase 4 |
| `python:S5850` en `domain/ai_assistant/answer.py:17` | MAJOR | Precedencia implicita del regex. No cambiaba el resultado | Grupos explicitos | `test_parse_model_answer_strips_markdown_fences`: protege el comportamiento; no falla sin el cambio porque no habia fallo funcional |
| `javascript:S9383` (28) en `frontend/js/` | MAJOR | Promesas sin manejar: un rechazo se perdia en silencio | `.catch(errorNoControlado)` | `node --check` en todos los archivos; sin pruebas automatizadas de JS |
| `Web:S5256` (2) en `pages/mercado.html` | MAJOR | Tablas sin `<th>` en el HTML estatico; el JS las rellena despues | Encabezado inicial que el JS reemplaza | Reanalisis de Sonar |
| `githubactions:S7637` y `S8541` en el workflow | MAJOR | Actions por etiqueta; pip podia ejecutar scripts de instalacion | Actions fijadas por SHA y `--only-binary :all:` | Ejecucion del CI |
| `githubactions:S8544` en el workflow | MAJOR | Versiones exactas, pero sin hashes | Abierto: se evaluara al cerrar la fase | Reanalisis de Sonar |
| `shell:S6505` en `scripts/run_all.sh` y `scripts/generar_evidencia.sh` | MAJOR | `npm install` ejecutaba scripts de ciclo de vida | `--ignore-scripts` | Reanalisis de Sonar |
| `python:S5332` (2) en `config.py:13` | MINOR | Origenes CORS `http://` solo de loopback para desarrollo | Abierto: revisar en la Fase 5 (CORS) | Pendiente |
| `pythonsecurity:S8701`, `S8707` y `S6350`; `javascript:S4036` en `scripts/` e `informe/` | MAJOR / MINOR | Herramientas locales de evidencia que ejecutan comandos por diseno; no son parte del producto | Fuera de `sonar.sources` al analizar desde CI. No se corrigen en el codigo | El alcance queda declarado en `sonar-project.properties` |
