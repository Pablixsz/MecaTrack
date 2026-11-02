"""Flujo real del frontend con JWT en el navegador: login, cabecera Bearer y redireccion por 401 y 403."""

import os
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evidence_index  # noqa: E402

FRONT = 'http://127.0.0.1:5500'
PHASE = 4


def shot(page, file, description):
    page.screenshot(path=os.path.join(evidence_index.IMG, file))
    evidence_index.register(file, PHASE, description, page.url)
    print(file, page.url)


def login(page, email):
    page.goto(f'{FRONT}/index.html')
    page.fill('#login-email', email)
    page.fill('#login-password', 'test1234')
    page.click('#form-login button[type=submit]')
    page.wait_for_url('**/pages/**')
    page.wait_for_load_state('networkidle')


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_context(viewport={'width': 1280, 'height': 800}).new_page()
    sent = []
    page.on('request', lambda r: sent.append(r) if ':5000/' in r.url and r.method != 'OPTIONS' else None)

    login(page, 'admin@demo.test')
    assert page.evaluate("sessionStorage.getItem('access_token')").count('.') == 2
    protected = [r for r in sent if r.url.endswith('/appointments')]
    assert protected and protected[0].headers['authorization'].startswith('Bearer ')
    print('Bearer en', protected[0].url)
    shot(page, '08a-frontend-login-admin.png', 'Frontend: login de admin; las peticiones llevan Authorization: Bearer')

    # 401: token invalido -> borra la sesion y vuelve al login
    page.evaluate("sessionStorage.setItem('access_token', 'a.b.c')")
    page.goto(f'{FRONT}/pages/dashboard-admin.html')
    page.wait_for_url('**/index.html')
    assert page.evaluate("sessionStorage.getItem('access_token')") is None
    shot(page, '08b-frontend-401-redirect.png', 'Frontend: con token invalido (401) borra la sesion y vuelve al login')

    # 403: un cliente pide un endpoint de gestion -> vuelve al login
    login(page, 'client@demo.test')
    status = page.evaluate("apiGet('/bays').catch(e => e.status)")
    page.wait_for_url('**/index.html')
    assert status == 403, status
    assert page.evaluate("sessionStorage.getItem('access_token')") is None
    shot(page, '08c-frontend-403-redirect.png', 'Frontend: un cliente recibe 403 en /bays y vuelve al login')
    browser.close()
