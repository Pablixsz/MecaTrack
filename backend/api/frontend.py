"""
Serves the vanilla HTML/CSS/JS frontend from the same Flask process, so the
whole system has ONE public URL (no CORS, no second service to deploy).

Only explicit prefixes are exposed (/, /index.html, /pages, /css, /js): a
catch-all route would turn every unknown API path into an HTML page.
send_from_directory rejects path traversal ('../').
"""

import os

from flask import Blueprint, current_app, send_from_directory

from api.rate_limit import limiter

frontend_bp = Blueprint('frontend', __name__)

# Security: the pages only load their own scripts (no inline <script>); styles allow the
# Google Fonts stylesheet and inline style attributes rendered by the JS (chart legends).
FRONTEND_CSP = ("default-src 'self'; script-src 'self'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; "
                "base-uri 'self'; form-action 'self'; frame-ancestors 'none'")


def _send(path):
    return send_from_directory(current_app.config['FRONTEND_DIR'], path, max_age=300)


@frontend_bp.route('/', methods=['GET'])
@frontend_bp.route('/index.html', methods=['GET'])
@limiter.exempt
def index():
    return _send('index.html')


@frontend_bp.route('/<any(pages, css, js):folder>/<path:filename>', methods=['GET'])
@limiter.exempt
def assets(folder, filename):
    return _send(f'{folder}/{filename}')


def frontend_enabled(app):
    directory = app.config.get('FRONTEND_DIR')
    return bool(directory) and os.path.isfile(os.path.join(directory, 'index.html'))
