# Registro de uso de IA - Guia 7

Herramienta usada: Claude Code (Claude Opus 5.5). GitHub Copilot no se ha usado hasta ahora.

| Fase | Que genero la IA | Que se reviso o corrigio |
|---|---|---|
| 0 | Diagnostico del repo y scripts de captura (`scripts/evidence/`) | El primer script de login aceptaba cualquier cuenta; se comprobo que la sesion abierta (`Pablixsz`) no tenia Settings en el repo de `pablo-rodriguez091004`, y se creo `Pablixsz/MecaTrack` por decision del usuario |
| 1 | `sonar-project.properties`, `.coveragerc` y paso de Sonar en el workflow | Pendiente de validar con el primer analisis real |
| 1 | Correcciones de los issues de Sonar y pruebas de regresion | Se reviso cada issue: los dos BLOCKER de XSS no eran HTML reflejado directo (la API responde JSON), asi que el arreglo real fue `nosniff`. La prueba del regex no falla sin el cambio y asi se documenta |
| 1 | Instalacion de pip con `--only-binary :all:` en el workflow | La IA escribio `:all:` sin comillas en YAML y el CI fallo al arrancar (run 41379928502, sin jobs). Se detecto porque el run no tenia nombre ni jobs; se corrigio con comillas y validacion local del YAML |
| 1 | `.catch(errorNoControlado)` en todas las lineas marcadas por Sonar | Correccion incorrecta de la IA: se aplico sin comprobar si la funcion era `async` y rompia 3 llamadas a `renderizarCitas` con `TypeError`. La detecto el reanalisis de SonarCloud (S3699); se revisaron las 26 llamadas y se corrigieron las 3 |
| 2 | `setup.cfg`, `scripts/mutation_score.py` y pruebas para matar mutantes | El primer intento fallo porque `test_architecture` lee el codigo instrumentado; se excluyo solo de mutmut. El score final se aclara como limitado al alcance configurado |
| 3 | Demo del fallo del gate en rama temporal | La primera demo eliminaba todas las pruebas de los modulos: fallo `mutmut run`, no el paso del score (run 41382364443), asi que no demostraba el requisito y se descarto. Se detecto al leer que paso habia fallado; se repitio conservando las pruebas de reglas puras (run 41382792374, score 6.5 %) |
