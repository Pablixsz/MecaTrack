# Pendientes manuales - Guia 7

## SONAR_TOKEN
1. En SonarCloud: avatar > My Account > Security > generar un token.
2. En GitHub: https://github.com/Pablixsz/MecaTrack/settings/secrets/actions > New repository secret > nombre `SONAR_TOKEN`.
Sin el secreto, el CI omite el analisis y no hay cobertura en SonarCloud.
