# MecaTrack

[![CI](https://github.com/Pablixsz/MecaTrack/actions/workflows/mecatrack-tests.yml/badge.svg?branch=mecatrack-final)](https://github.com/Pablixsz/MecaTrack/actions/workflows/mecatrack-tests.yml) [![Quality Gate](https://sonarcloud.io/api/project_badges/measure?project=Pablixsz_MecaTrack&metric=alert_status)](https://sonarcloud.io/summary/overall?id=Pablixsz_MecaTrack) ![Mutation score](https://img.shields.io/badge/mutation%20score-98.4%25-brightgreen)

Sistema de gestión de citas y seguimiento para un taller mecánico. Proyecto final individual de **Taller de Programación**.

- **Clientes:** se registran, agregan sus vehículos, consultan el catálogo, agendan citas, pagan el depósito (simulado) y siguen el estado de su servicio.
- **Mecánicos:** ven las citas que tienen asignadas, cambian su estado y registran cada paso del servicio (con los repuestos usados, que se descuentan del inventario).
- **Dueño (owner):** tiene una vista global de las citas y gestiona bahías, repuestos, servicios y mecánicos.

Cuando se agenda una cita, el **motor de agendamiento** (`backend/domain/scheduling/allocation.py`) asigna solo una bahía y un mecánico libres, sin que se crucen los horarios.

## Security

> Written in English, as required for this deliverable.

- **Authentication:** `POST /api/auth/login` returns a short-lived JWT (15 minutes by default) with the role as a claim. Send it as `Authorization: Bearer <token>`. `JWT_SECRET_KEY` is required and only comes from the environment.
- **Authorization:** `@role_required` protects each route (`client`, `mechanic`, `admin`, `owner`). A missing or invalid token gets 401 and a wrong role gets 403.
- **Token storage:** the frontend keeps the token in `sessionStorage`, not in `localStorage` or a cookie. It is cleared when the tab closes and there is no cookie for CSRF to abuse. The trade-off is that a script running on the page could read it, so rendered data is escaped.
- **Controls:** see [docs/lab7/owasp-controls.md](docs/lab7/owasp-controls.md) for the OWASP API Security Top 10 2023 table, with files, tests and known limitations.
- **Pipeline:** CI runs the tests, SonarCloud and mutation testing, and fails if the mutation score is below 50 %.
- **Reporting:** please open a private security advisory on this repository instead of a public issue.

## Stack

| Capa | Tecnología |
|---|---|
| Frontend | HTML / CSS / JavaScript vanilla (sin frameworks) — `127.0.0.1:5500` (o Live Server) |
| Backend | Flask 3 + Flask-SQLAlchemy + Flask-Migrate (Alembic) + Flask-JWT-Extended (Bearer) + Flask-CORS — `127.0.0.1:5000` |
| Base de datos | PostgreSQL (`taller_mecanico`) |
| Pruebas | pytest (integración) + GitHub Actions |

## Estructura

```
PROYECTO_FINAL/
├── backend/                   # Arquitectura hexagonal (Guía 6): ver docs/adr/
│   ├── app.py                 # app factory: config + extensiones + bootstrap + api
│   ├── bootstrap.py           # composition root: crea adaptadores y los inyecta
│   ├── config.py              # Config / TestConfig
│   ├── domain/                # núcleo, solo Python estándar: entidades, reglas y puertos (ABC)
│   │   └── identity, catalog, scheduling, payments, tracking, ai_assistant   (bounded contexts)
│   ├── application/           # casos de uso por contexto, dependencias por constructor
│   ├── api/                   # adaptador HTTP: legacy/ (frontend) y v1/ (OpenAPI)
│   ├── infrastructure/        # adaptadores: persistence/ (modelos y repos SQLAlchemy), llm/, security/
│   ├── migrations/            # Alembic: esquema inicial (= schema.sql) + índices
│   └── tests/                 # integración (pytest) + reglas de arquitectura
├── frontend/
│   ├── index.html             # login / registro
│   ├── pages/                 # catálogo, calendario, historial, panel mecánico, panel dueño
│   ├── js/                    # un archivo por página + api.js (wrapper de fetch)
│   └── css/styles.css
├── database/                  # schema.sql y seed.sql
├── scripts/start-backend.sh
└── docs/
```

## Puesta en marcha

### Requisitos

- Python 3.10 o superior
- PostgreSQL corriendo en `127.0.0.1:5432`
- Un servidor estático para el frontend (Live Server de VSCode o `python3 -m http.server`)

### 1. Base de datos

Si la base todavía no existe, créala y cárgala con **una** de estas dos opciones:

```bash
createdb -h 127.0.0.1 -U postgres taller_mecanico

# Opción A: con migraciones (recomendada)
./scripts/start-backend.sh --migrate          # crea las tablas con Alembic
psql -h 127.0.0.1 -U postgres -d taller_mecanico -f database/seed.sql

# Opción B: con el script SQL
psql -h 127.0.0.1 -U postgres -d taller_mecanico -f database/schema.sql
psql -h 127.0.0.1 -U postgres -d taller_mecanico -f database/seed.sql
```

> **¿Tu base ya existía (creada con `schema.sql`)?** Sus tablas coinciden con la migración inicial (`26b91cd3e584`). Para que Alembic lo sepa y luego aplique la segunda migración (índices), ejecuta una sola vez:
> ```bash
> cd backend
> venv/bin/flask --app app db stamp 26b91cd3e584   # marca la base como "en la migración inicial"
> venv/bin/flask --app app db upgrade              # aplica 6a4f4ff49bfe (índices)
> ```

> `seed.sql` trae `password_hash` de ejemplo que no sirven para iniciar sesión. Los usuarios de prueba deben tener la contraseña `test1234` (hash generado con `werkzeug.security.generate_password_hash`).

### 2. Backend

```bash
./scripts/start-backend.sh
```

La primera vez, el script crea `backend/venv`, instala las dependencias y copia `.env.example` a `.env`. Edita `backend/.env`:

```
SECRET_KEY=una-clave-aleatoria
DATABASE_URL=postgresql://postgres:TU_CONTRASENA@127.0.0.1:5432/taller_mecanico
```

Luego vuelve a ejecutar el script. La API queda en `http://127.0.0.1:5000`.

<details>
<summary>Arranque manual (sin el script / Windows)</summary>

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # Windows: copy .env.example .env
python app.py
```
</details>

### 3. Frontend

Sírvelo con un servidor estático en el **puerto 5500 o 5501** (`127.0.0.1` o `localhost`). El backend acepta esos cuatro orígenes; puedes cambiarlos con la variable `CORS_ORIGINS` (lista separada por comas). **No abras `index.html` con doble clic** (`file://`): el navegador bloquea las peticiones a la API.

```bash
cd frontend && python3 -m http.server 5500 --bind 127.0.0.1
```

Abre `http://127.0.0.1:5500/index.html` en Firefox o Chrome. Con Live Server de VSCode: clic derecho en `frontend/index.html` → *Open with Live Server* (si el 5500 está ocupado usa el 5501, p. ej. `http://127.0.0.1:5501/frontend/index.html`, abriendo `PROYECTO_FINAL` como carpeta en VS Code).

### Usuarios de prueba (contraseña `test1234`)

| Rol | Correo | Entra a |
|---|---|---|
| Dueño | carlos.owner@tallermecanico.com | `pages/dashboard-admin.html` |
| Mecánico | andres.mecanico@tallermecanico.com | `pages/dashboard-empleado.html` |
| Cliente | laura.cliente@gmail.com | `pages/catalogo.html` |
| Administrador | admin@tallermecanico.com | `pages/dashboard-admin.html` (pestaña **Recepción**: registra clientes y vehículos y agenda citas a su nombre) |

El administrador se crea con `backend/venv/bin/python scripts/crear_admin.py` (no duplica si ya existe).

## Pruebas

Las pruebas de integración corren contra una base **aparte**, `taller_mecanico_test`, y nunca tocan `taller_mecanico`: `conftest.py` aborta si el nombre de la base no termina en `_test`. El esquema se crea con la migración de Alembic, así que las pruebas también comprueban que la migración esté bien.

```bash
createdb -h 127.0.0.1 -U postgres taller_mecanico_test   # solo la primera vez
cd backend
venv/bin/pip install -r requirements-dev.txt
venv/bin/python -m pytest
```

Para usar otra base, define `TEST_DATABASE_URL`.

Las pruebas están en dos carpetas:

- `tests/unit/`: casos de uso y reglas de dominio con las dependencias simuladas (`unittest.mock.create_autospec` sobre cada puerto). No necesitan PostgreSQL ni red y corren en menos de 1 s: `venv/bin/python -m pytest tests/unit`.
- `tests/integration/`: Flask + PostgreSQL reales (la tabla de abajo).

| Prueba | Qué verifica |
|---|---|
| `test_login_and_role_based_access` | login/logout, 401 sin sesión, 403 por rol, el dueño crea bahías |
| `test_booking_flow_assigns_resources_and_deposit_confirms` | se asignan bahía y mecánico, se calculan depósito (30 %) y saldo, pagar el depósito confirma la cita, el listado no tiene N+1 (`joinedload`, ≤ 2 SELECT) |
| `test_scheduling_conflict_returns_409_and_cancel_frees_slot` | un cruce de horario da 409, `[inicio, fin)` permite citas seguidas, cancelar libera la franja, una bahía en mantenimiento no se asigna |
| `integration/test_legacy_routes.py` | contrato HTTP de negocio, mecánicos, repuestos, servicios, vehículos, seguimiento (stock) y estados de cita; validado contra el código previo al refactor |
| `unit/test_appointment_service.py`, `unit/test_payment_service.py` | DI por constructor: agendar, cancelar y pagar con repositorios, unit of work y reloj simulados |
| `unit/test_architecture.py` | reglas de dependencias: `domain` solo usa la librería estándar, `application` no usa Flask/SQLAlchemy/IO, `api` no importa `infrastructure` |

GitHub Actions ejecuta las pruebas con un servicio PostgreSQL en cada push o PR que toque `backend/**` (ver `.github/workflows/mecatrack-tests.yml`).

## Migraciones (Flask-Migrate)

| Revisión | Descripción |
|---|---|
| `26b91cd3e584` | Esquema inicial: las 10 tablas, equivalente a `database/schema.sql` |
| `6a4f4ff49bfe` | Índices para el motor de agendamiento (bahía/mecánico + horario) y para las FK de pagos y seguimiento |

```bash
cd backend
venv/bin/flask --app app db migrate -m "descripcion"   # tras cambiar un modelo
venv/bin/flask --app app db upgrade                    # aplicar
venv/bin/flask --app app db downgrade                  # revertir la última
```

## API (resumen)

| Recurso | Endpoints |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` |
| Vehículos | `GET/POST /vehicles`, `GET/PUT/DELETE /vehicles/<id>` |
| Servicios | `GET /services` (público), `GET /services/manage`, `POST /services`, `PUT/DELETE /services/<id>` |
| Bahías | `GET/POST /bays`, `PUT /bays/<id>` |
| Repuestos | `GET /parts[?include_inactive=1]`, `POST /parts`, `PUT /parts/<id>` |
| Negocio | `GET/PUT /businesses/mine`, `GET/POST /businesses/mechanics`, `PUT /businesses/mechanics/<id>` |
| Citas | `GET/POST /appointments`, `GET/DELETE /appointments/<id>`, `PUT /appointments/<id>/status` |
| Pagos | `GET /payments/appointment/<id>`, `POST /payments/<id>/pay` |
| Seguimiento | `GET/POST /tracking/appointment/<id>` |
| Mercado (v1) | `GET /api/v1/market/sources`, `POST /api/v1/market/refresh`, `GET /api/v1/market/analytics/{fleet-age,motorization,age-distribution}` |

Las rutas antiguas responden los errores como `{"error": "mensaje"}`; las de `/api/v1` (documentadas en `/docs`) como `{"code", "message", "details"}`.

### Datos abiertos y DuckDB (Guía 6)

El panel **Mercado** (dueño/admin, `frontend/pages/mercado.html`) descarga datos abiertos de Colombia y los analiza con DuckDB:

- **RUNT, parque automotor** (MinTransporte, datos.gov.co `u3vn-bdcy`), **DIVIPOLA** (DANE, `gdxc-w37w`) y **población CNPV 2018** (geoportal ArcGIS del DANE).
- Cada host tiene un **circuit breaker** (CLOSED → OPEN → HALF_OPEN) y las fallas transitorias se reintentan con **backoff exponencial + jitter** (`backend/infrastructure/resilience/`).
- Las descargas quedan en `backend/var/market_data/` (no se versionan). La primera vez pulsa **Actualizar datos**, o llama a `POST /api/v1/market/refresh`.
- Demo controlada de la resiliencia con red real: `backend/venv/bin/python scripts/demo_resilience.py`.
- `./scripts/demo.sh` levanta la demo para el video (`--breaker-abierto`: datos.gov.co apunta a un host `.invalid`; `--ciclo`: ciclo completo del breaker en la terminal).
- `./scripts/generar_evidencia.sh` regenera en un solo paso las pruebas, las 18 capturas de `docs/evidencia/` y el informe `informe/Informe_Guia6_MecaTrack.docx`.
- Decisión de arquitectura: `docs/adr/0001-hexagonal-architecture.md`. Trazabilidad del uso de IA: `docs/USO_DE_IA.md`.
