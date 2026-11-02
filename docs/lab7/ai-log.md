# Registro de uso de IA - Guia 7

Herramienta usada: Claude Code (Claude Opus 5.5). GitHub Copilot no se ha usado hasta ahora.

| Fase | Que genero la IA | Que se reviso o corrigio |
|---|---|---|
| 0 | Diagnostico del repo y scripts de captura (`scripts/evidence/`) | El primer script de login aceptaba cualquier cuenta; se comprobo que la sesion abierta (`Pablixsz`) no tenia Settings en el repo de `pablo-rodriguez091004`, y se creo `Pablixsz/MecaTrack` por decision del usuario |
| 1 | `sonar-project.properties`, `.coveragerc` y paso de Sonar en el workflow | Pendiente de validar con el primer analisis real |
| 1 | Correcciones de los issues de Sonar y pruebas de regresion | Se reviso cada issue: los dos BLOCKER de XSS no eran HTML reflejado directo (la API responde JSON), asi que el arreglo real fue `nosniff`. La prueba del regex no falla sin el cambio y asi se documenta |
| 1 | Instalacion de pip con `--only-binary :all:` en el workflow | La IA escribio `:all:` sin comillas en YAML y el CI fallo al arrancar (run 41379928502, sin jobs). Se detecto porque el run no tenia nombre ni jobs; se corrigio con comillas y validacion local del YAML |
