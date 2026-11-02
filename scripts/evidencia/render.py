"""
Convierte salidas REALES de terminal y fragmentos REALES de codigo en PNG.

- Terminal: el texto se escapa tal cual (con colores ANSI -> HTML). No se
  edita ninguna linea; solo se puede recortar por un rango explicito, y en
  ese caso la imagen lo dice ("lineas X-Y de N").
- Codigo: Pygments resalta las lineas pedidas de un archivo del repo,
  mostrando la ruta y los numeros de linea reales.
- Antes de renderizar se verifica que el contenido no incluya valores
  secretos de backend/.env (contraseña de la BD, SECRET_KEY, API keys).

Uso desde capturar.py; tambien sirve suelto para depurar.
"""

import html
import os
import re

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_for_filename

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
ENV_FILE = os.path.join(ROOT, 'backend', '.env')

ANSI_COLORS = {30: '#94a3b8', 31: '#f87171', 32: '#4ade80', 33: '#facc15', 34: '#60a5fa', 35: '#e879f9',
               36: '#22d3ee', 37: '#e2e8f0', 90: '#94a3b8', 91: '#fca5a5', 92: '#86efac', 93: '#fde047',
               94: '#93c5fd', 95: '#f0abfc', 96: '#67e8f9', 97: '#f8fafc'}
ANSI_RE = re.compile(r'\x1b\[([0-9;]*)m')


class SecretLeak(Exception):
    pass


def secret_values():
    """Valores sensibles de backend/.env (nunca deben aparecer en una captura)."""
    values = set()
    if not os.path.exists(ENV_FILE):
        return values
    for line in open(ENV_FILE, encoding='utf-8'):
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        value = value.strip().strip('"\'')
        if not value:
            continue
        if any(word in key.upper() for word in ('KEY', 'SECRET', 'TOKEN', 'PASSWORD')):
            values.add(value)
        if key.strip().endswith('DATABASE_URL'):
            match = re.match(r'^[a-z+]+://[^:/@]+:([^@]+)@', value)
            if match:
                values.add(match.group(1))  # solo la contraseña: el usuario 'postgres' no es secreto
    return {v for v in values if len(v) >= 6}


def assert_no_secrets(text, label):
    for value in secret_values():
        if value in text:
            raise SecretLeak(f'{label}: contiene un valor de backend/.env; no se guarda la captura')


def ansi_to_html(text):
    out, open_spans = [], 0
    position = 0
    for match in ANSI_RE.finditer(text):
        out.append(html.escape(text[position:match.start()]))
        position = match.end()
        codes = [int(c) for c in match.group(1).split(';') if c] or [0]
        for code in codes:
            if code == 0:
                out.append('</span>' * open_spans)
                open_spans = 0
            elif code == 1:
                out.append('<span style="font-weight:700">')
                open_spans += 1
            elif code in ANSI_COLORS:
                out.append(f'<span style="color:{ANSI_COLORS[code]}">')
                open_spans += 1
    out.append(html.escape(text[position:]))
    out.append('</span>' * open_spans)
    return ''.join(out)


def strip_ansi(text):
    return ANSI_RE.sub('', text)


def terminal_panel(command, output, note=''):
    """Panel tipo terminal. `command` se muestra como prompt; `output` va literal."""
    return {'kind': 'terminal', 'command': command, 'output': output, 'note': note}


def code_panel(relative_path, start, end, note=''):
    """Panel con las lineas [start, end] (1-indexadas, inclusivas) de un archivo del repo."""
    path = os.path.join(ROOT, relative_path)
    lines = open(path, encoding='utf-8').read().splitlines()
    end = min(end, len(lines))
    return {'kind': 'code', 'path': relative_path, 'start': start, 'end': end, 'total': len(lines),
            'source': '\n'.join(lines[start - 1:end]), 'note': note}


def find_lines(relative_path, start_pattern, end_pattern=None, include_end=True, after=0):
    """Numeros de linea [inicio, fin] entre dos patrones (regex) de un archivo."""
    lines = open(os.path.join(ROOT, relative_path), encoding='utf-8').read().splitlines()
    start = next(i for i, line in enumerate(lines, 1) if i > after and re.search(start_pattern, line))
    if end_pattern is None:
        return start, len(lines)
    end = next(i for i, line in enumerate(lines, 1) if i > start and re.search(end_pattern, line))
    return start, end if include_end else end - 1


CSS = """
* { box-sizing: border-box; }
body { margin: 0; padding: 24px; background: #e9edf3; font-family: Inter, 'Segoe UI', system-ui, sans-serif; width: %(width)dpx; }
h1 { font-size: 18px; margin: 0 0 4px; color: #0f172a; }
.sub { font-size: 13px; color: #475467; margin: 0 0 16px; }
.panel { border-radius: 10px; overflow: hidden; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(15,23,42,.18); }
.bar { display: flex; align-items: center; gap: 8px; padding: 9px 14px; background: #1e293b; color: #cbd5e1; font-size: 12.5px; font-family: 'JetBrains Mono', 'DejaVu Sans Mono', monospace; }
.dot { width: 11px; height: 11px; border-radius: 50%%; display: inline-block; }
.bar .title { margin-left: 6px; white-space: pre-wrap; word-break: break-all; }
.term { margin: 0; padding: 14px 16px; background: #0f172a; color: #e2e8f0; font: 12.5px/1.5 'JetBrains Mono', 'DejaVu Sans Mono', Menlo, monospace; white-space: pre-wrap; word-break: break-word; }
.prompt { color: #4ade80; }
.note { background: #fff7e6; color: #7a4b00; font-size: 12px; padding: 7px 14px; border-top: 1px solid #f3d9a4; }
.code .highlight pre { margin: 0; padding: 12px 0; font: 12.5px/1.55 'JetBrains Mono', 'DejaVu Sans Mono', Menlo, monospace; }
.code .highlight { background: #0d1117; }
.code td.linenos { background: #0d1117; color: #6e7681; text-align: right; padding: 0 10px 0 14px; user-select: none; vertical-align: top; }
.code td.linenos pre { margin: 0; padding: 12px 0; font: 12.5px/1.55 'JetBrains Mono', 'DejaVu Sans Mono', Menlo, monospace; color: #6e7681; }
.code table { border-collapse: collapse; width: 100%%; background: #0d1117; }
/* Sin ligaduras: "->", "!=" o "===" se ven tal como estan escritos. */
.term, .code pre, .bar { font-variant-ligatures: none; font-feature-settings: "liga" 0, "calt" 0; }
.row { display: flex; gap: 16px; align-items: flex-start; }
.row > .panel { flex: 1 1 0; min-width: 0; }
.code td.code { width: 100%%; padding-left: 8px; }
"""


def _panel_html(panel):
    if panel['kind'] == 'terminal':
        commands = panel['command'] if isinstance(panel['command'], list) else [panel['command']]
        prompts = '\n'.join(f'<span class="prompt">$</span> {html.escape(c)}' for c in commands)
        body = f'<pre class="term">{prompts}\n{ansi_to_html(panel["output"].rstrip())}</pre>'
        title = 'terminal'
    else:
        lexer = get_lexer_for_filename(panel['path'])
        formatter = HtmlFormatter(style='github-dark', linenos='table', linenostart=panel['start'])
        body = f'<div class="code">{highlight(panel["source"], lexer, formatter)}</div>'
        title = f'{panel["path"]}  ·  líneas {panel["start"]}-{panel["end"]} de {panel["total"]}'
    note = f'<div class="note">{html.escape(panel["note"])}</div>' if panel.get('note') else ''
    dots = ''.join(f'<span class="dot" style="background:{c}"></span>' for c in ('#f87171', '#facc15', '#4ade80'))
    return f'<div class="panel"><div class="bar">{dots}<span class="title">{html.escape(title)}</span></div>{body}{note}</div>'


def _block_html(item):
    """Un panel, o una lista de paneles que se muestran lado a lado."""
    if isinstance(item, (list, tuple)):
        return f'<div class="row">{"".join(_panel_html(p) for p in item)}</div>'
    return _panel_html(item)


def _flatten(panels):
    for item in panels:
        yield from (item if isinstance(item, (list, tuple)) else [item])


def build_html(title, subtitle, panels, width=1180):
    style = CSS % {'width': width} + HtmlFormatter(style='github-dark').get_style_defs('.code .highlight')
    content = ''.join(_block_html(p) for p in panels)
    return (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><style>{style}</style></head><body>'
            f'<h1>{html.escape(title)}</h1><p class="sub">{html.escape(subtitle)}</p>{content}</body></html>')


def render(browser, out_png, title, subtitle, panels, width=1180):
    raw = '\n'.join(str(value) for panel in _flatten(panels) for value in panel.values())
    assert_no_secrets(f'{raw}\n{title}\n{subtitle}', os.path.basename(out_png))
    page = browser.new_page(viewport={'width': width + 48, 'height': 100}, device_scale_factor=2)
    page.set_content(build_html(title, subtitle, panels, width))
    page.screenshot(path=out_png, full_page=True)
    page.close()
