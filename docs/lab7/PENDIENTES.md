# Pendientes manuales - Guia 7

Completa `docs/lab7/report-config.json` y regenera el informe con `node scripts/build_report.js` (requiere LibreOffice y `pdftotext`).

- [ ] **Codigos estudiantiles** de los tres integrantes: campo `authors[].code`.
- [ ] **Nombre del docente:** campo `teacher`.
- [ ] **Enlace del video de YouTube:** campo `videoUrl`. Guion opcional en `docs/lab7/video-script.md`.
- [ ] **Indice en Word:** los numeros de pagina se calculan con LibreOffice. Al abrir el informe en Word, comprueba que coincidan; si Word pagina distinto, ajustalos a mano.

## Decisiones que quedan en tus manos

- [ ] Revisar los 6 PR abiertos de Dependabot. Ojo con `duckdb 2.0.0`, que es un cambio de version mayor.
- [ ] Al terminar: revocar la deploy key `mecatrack-lab7-deploy` en Settings > Deploy keys, borrar `~/.ssh/mecatrack_deploy_key` y `~/.mecatrack-firefox-profile`.
