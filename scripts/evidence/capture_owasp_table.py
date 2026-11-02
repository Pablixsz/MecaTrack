"""Renderiza como imagen la tabla real de docs/lab7/owasp-controls.md."""

import html
import os
import re
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evidence_index  # noqa: E402

SOURCE = os.path.join(evidence_index.ROOT, 'docs', 'lab7', 'owasp-controls.md')
FILE = '09a-owasp-table.png'


def cell(text):
    escaped = html.escape(text.strip()).replace('&lt;br&gt;', '<br>')
    return re.sub(r'`([^`]+)`', r'<code>\1</code>', escaped)


rows = [line.strip('|').split(' | ') for line in open(SOURCE, encoding='utf-8')
        if line.startswith('| ') and not line.startswith('|---')]
head = ''.join(f'<th>{cell(c)}</th>' for c in rows[0])
body = ''.join('<tr>' + ''.join(f'<td>{cell(c)}</td>' for c in row) + '</tr>' for row in rows[1:])
page_html = f"""<!doctype html><meta charset="utf-8"><style>
body{{font:13px/1.4 Inter,'Segoe UI',sans-serif;margin:20px;color:#0f172a;background:#fff}}
table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #cbd5e1;padding:7px 9px;vertical-align:top;text-align:left}}
th{{background:#1e293b;color:#fff}}code{{font:11px 'DejaVu Sans Mono',monospace;word-break:break-all}}
td:nth-child(1){{width:16%;font-weight:600}}td:nth-child(2){{width:34%}}td:nth-child(3){{width:26%}}
</style><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"""

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1400, 'height': 100}, device_scale_factor=2)
    page.set_content(page_html)
    page.screenshot(path=os.path.join(evidence_index.IMG, FILE), full_page=True)
    browser.close()
evidence_index.register(FILE, 5, 'OWASP API Security Top 10 2023: table of implemented controls', 'docs/lab7/owasp-controls.md')
print(FILE, len(rows) - 1, 'controls')
