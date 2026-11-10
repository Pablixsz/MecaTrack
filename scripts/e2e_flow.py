"""
End-to-end check of MecaTrack through the REAL browser UI (headless Chromium).

Flow: client logs in -> books an appointment from the catalog -> pays the
simulated deposit (appointment becomes 'confirmed') -> mechanic moves it to
'in_progress', adds a tracking entry and completes it -> client sees the
tracking -> owner and admin open their dashboards.

It fails on any step that does not happen, on any Content-Security-Policy
violation and on any uncaught JS error, and takes one screenshot per step.

Works against any deployment that serves the frontend and the API on the same
origin (gunicorn locally, docker compose, Render). Uses the seed users
(database/seed.sql, password test1234), so run it only on dev/demo data.

    backend/venv/bin/python scripts/e2e_flow.py --base-url http://localhost:8000 \
        --out docs/evidence --prefix 03-compose
"""

import argparse
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

PASSWORD = 'test1234'
CLIENT = 'laura.cliente@gmail.com'
MECHANIC = 'andres.mecanico@tallermecanico.com'
OWNER = 'carlos.owner@tallermecanico.com'
ADMIN = 'admin@tallermecanico.com'
TIMEOUT_MS = 30_000  # generous: a free PaaS instance may be waking up


class Run:
    def __init__(self, page, base, out, prefix):
        self.page, self.base, self.out, self.prefix = page, base.rstrip('/'), out, prefix
        self.step = 0
        self.problems = []
        page.on('pageerror', lambda exc: self.problems.append(f'JS error: {exc}'))
        page.on('console', self._console)

    def _console(self, msg):
        if 'Content Security Policy' in msg.text or 'Content-Security-Policy' in msg.text:
            self.problems.append(f'CSP violation: {msg.text}')

    def shot(self, name):
        self.step += 1
        path = self.out / f'{self.prefix}-{self.step:02d}-{name}.png'
        self.page.screenshot(path=str(path), full_page=True)
        print(f'  [ok] {name:<28} -> {path}')

    def login(self, email, landing):
        page = self.page
        page.goto(f'{self.base}/index.html')
        page.evaluate('sessionStorage.clear()')
        page.goto(f'{self.base}/index.html')
        page.fill('#login-email', email)
        page.fill('#login-password', PASSWORD)
        page.click('#form-login button[type=submit]')
        page.wait_for_url(f'**/pages/{landing}', timeout=TIMEOUT_MS)
        page.wait_for_load_state('networkidle')


def free_slot():
    """A future slot unlikely to clash with earlier runs (one mechanic, two bays in the seed)."""
    # Not security related: random test data only, so the PRNG warnings are suppressed.
    day = datetime.now() + timedelta(days=random.randint(20, 400))  # nosec B311 # NOSONAR
    hour, minute = random.randint(7, 16), random.choice((0, 30))  # nosec B311 # NOSONAR
    return day.replace(hour=hour, minute=minute, second=0, microsecond=0)


def run(base, out, prefix):
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={'width': 1280, 'height': 900}, locale='es-CO')
        page.set_default_timeout(TIMEOUT_MS)
        r = Run(page, base, out, prefix)

        # 1. Client: login -> catalog
        r.login(CLIENT, 'catalogo.html')
        expect(page.locator('.btn-agendar').first).to_be_visible()
        r.shot('client-catalog')

        # 2. Book the first service
        page.locator('.btn-agendar').first.click()
        page.wait_for_url('**/calendario.html?service_id=*')
        page.wait_for_load_state('networkidle')
        if page.locator('#bloque-nuevo-vehiculo').is_visible():
            plate = f'E2E{random.randint(100, 999)}'  # nosec B311 # NOSONAR
            page.fill('#veh-placa', plate)
            page.fill('#veh-marca', 'Renault')
            page.fill('#veh-modelo', 'Logan')
            page.fill('#veh-anio', '2019')
        page.fill('#input-fecha-hora', free_slot().strftime('%Y-%m-%dT%H:%M'))
        with page.expect_response(lambda resp: resp.url.endswith('/appointments')
                                  and resp.request.method == 'POST') as booked:
            page.click('#btn-confirmar')
        assert booked.value.status == 201, f'booking answered {booked.value.status}: {booked.value.text()}'
        appointment_id = booked.value.json()['appointment_id']
        expect(page.locator('#agendar-exito')).not_to_be_empty()
        r.shot(f'client-booked-{appointment_id}')

        # 3. Pay the simulated deposit -> appointment confirmed
        page.goto(f'{r.base}/pages/historial-cliente.html')
        page.wait_for_load_state('networkidle')
        payments = page.evaluate(f'apiGet("/payments/appointment/{appointment_id}")')
        deposit = next(p for p in payments if p['payment_type'] == 'deposit')
        with page.expect_response(lambda resp: resp.url.endswith(f'/payments/{deposit["payment_id"]}/pay')) as paid:
            page.click(f'.btn-pagar[data-payment-id="{deposit["payment_id"]}"]')
        assert paid.value.status == 200, f'payment answered {paid.value.status}'
        page.wait_for_load_state('networkidle')
        status = page.evaluate(f'apiGet("/appointments/{appointment_id}")')['status']
        assert status == 'confirmed', f'after the deposit the appointment is {status}'
        r.shot('client-deposit-paid')

        # 4. Mechanic: in_progress -> tracking entry -> completed
        r.login(MECHANIC, 'dashboard-empleado.html')
        card = page.locator(f'.tarjeta-servicio[data-appointment-id="{appointment_id}"]')
        expect(card).to_be_visible()

        def set_status(value):
            card.locator('.select-estado-cita').select_option(value)
            card.locator('.btn-guardar-estado').click()
            expect(card.locator('.mensaje-exito')).to_have_text('Estado actualizado.')

        set_status('in_progress')
        card.locator('.card-footer .btn-toggle-seguimiento').click()
        card.locator('.tracking-estado').select_option('in_repair')
        card.locator('.tracking-notas').fill('E2E: brake pads replaced, test drive pending')
        with page.expect_response(lambda resp: f'/tracking/appointment/{appointment_id}' in resp.url
                                  and resp.request.method == 'POST') as tracked:
            card.locator('.form-seguimiento button[type=submit]').click()
        assert tracked.value.status == 201, f'tracking answered {tracked.value.status}: {tracked.value.text()}'
        page.wait_for_load_state('networkidle')
        card = page.locator(f'.tarjeta-servicio[data-appointment-id="{appointment_id}"]')
        r.shot('mechanic-tracking')
        set_status('completed')

        # 5. Client sees the tracking entry
        r.login(CLIENT, 'catalogo.html')
        tracking = page.evaluate(f'apiGet("/tracking/appointment/{appointment_id}")')
        assert any('E2E' in (t.get('notes') or '') for t in tracking), tracking
        page.goto(f'{r.base}/pages/historial-cliente.html')
        page.wait_for_load_state('networkidle')
        r.shot('client-history')

        # 6. Owner and admin dashboards
        for email, name in ((OWNER, 'owner'), (ADMIN, 'admin')):
            r.login(email, 'dashboard-admin.html')
            r.shot(f'{name}-dashboard')

        browser.close()

    if r.problems:
        print('\nProblems found in the browser:')
        for problem in r.problems:
            print(f'  - {problem}')
        return 1
    print(f'\nE2E OK: appointment #{appointment_id} booked, paid, tracked and completed; no CSP or JS errors.')
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--base-url', default='http://localhost:8000')
    parser.add_argument('--out', default='docs/evidence', type=Path)
    parser.add_argument('--prefix', default='e2e')
    args = parser.parse_args()
    sys.exit(run(args.base_url, args.out, args.prefix))
