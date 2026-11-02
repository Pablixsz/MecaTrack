# MecaTrack: que se hizo, por que y que mejoro

MecaTrack funcionaba y tenia pruebas, pero su calidad no se media de forma continua y su seguridad dependia de cookies de sesion y de pocos controles. Esta guia convirtio esa confianza en verificaciones automaticas: si algo se degrada, el pipeline lo avisa.

## Calidad

**SonarCloud.** Se conecto al CI con cobertura. *Por que:* una revision manual no detecta todo de forma constante. *Mejora:* de 32 bugs y 15 vulnerabilidades a ninguno abierto de esos tipos, con 97.2 % de cobertura y Quality Gate aprobado. Tambien revelo 4 CVE en dependencias, ya actualizadas. Cinco hallazgos se cerraron con justificacion escrita, no con cambios de codigo, y las herramientas de `scripts/` e `informe/` quedaron fuera del analisis.

**Mutation testing.** mutmut altera el codigo a proposito y comprueba si alguna prueba lo nota. *Por que:* una cobertura de 98 % solo dice que una linea se ejecuto, no que su resultado se verifico. *Mejora:* de 62.6 % a 98.4 % en agendamiento y pagos, cerrando huecos reales: una funcion no tenia ninguna prueba.

**CI.** El build falla si ese score baja de 50 %, y se demostro con una caida real a 6.5 %. *Mejora:* la calidad de las pruebas ya no puede degradarse sin que se note.

## Seguridad

**JWT y roles.** Las cookies de sesion se reemplazaron por tokens de 15 minutos en la cabecera, con el rol como claim. *Por que:* la cookie exponia la API a CSRF. *Mejora:* desaparece la causa de ese riesgo, en vez de parchearla. Ademas, cerrar sesion revoca el token, y una cuenta desactivada o con otro rol pierde el acceso de inmediato.

**OWASP API Security Top 10 2023.** Hay controles con pruebas para 9 de los 10 riesgos. *Por que:* muchos ataques a APIs abusan de permisos y de la logica del negocio. *Mejora:*
- Un cliente no puede ver datos de otro.
- El login se bloquea tras 5 intentos por minuto y no revela que cuentas existen.
- Las respuestas nunca incluyen `password_hash`.
- Hay limites de tamano y de paginacion, cabeceras de seguridad y errores sin detalles internos.
- Nadie puede confirmar una cita sin deposito pagado, y un cliente no puede acaparar mas de 5 citas activas.

**CodeQL y Dependabot.** *Por que:* las vulnerabilidades tambien llegan con el codigo nuevo y con las dependencias. *Mejora:* cada push se analiza (0 alertas, 138 archivos escaneados) y Dependabot propone actualizaciones por si solo: abrio 9 PR, de los cuales 6 siguen abiertos para revision.

## Resultado

| Metrica | Antes | Despues |
|---|---|---|
| Pruebas | 128 | 241 |
| Bugs / vulnerabilidades abiertos en Sonar | 32 / 15 | 0 / 0 |
| Score de mutacion (agendamiento y pagos) | 62.6 % | 98.4 % |
| CVE en dependencias | 4 | 0 |
| Autenticacion | Cookie de sesion | JWT con revocacion y roles |

## Limitaciones

- La revocacion de tokens y el limite de intentos viven en la memoria de un solo proceso; con varios servidores haria falta un almacen compartido como Redis.
- La paginacion recorta la respuesta, no la consulta a la base de datos.
- El frontend no tiene pruebas automatizadas de JavaScript.
- El score de mutacion cubre el agendamiento y los pagos, no todo el backend.
