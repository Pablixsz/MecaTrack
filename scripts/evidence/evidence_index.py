"""
Registro de evidencias: docs/lab7/evidence/index.json (Guia 7, con img/ y outputs/).

Con EVIDENCE_DIR=docs/evidence (Guia 8) todo queda plano en esa carpeta: PNG, TXT e index.json.
"""

import json
import os
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if os.environ.get('EVIDENCE_DIR'):
    EVIDENCE = os.path.join(ROOT, os.environ['EVIDENCE_DIR'])
    IMG = OUTPUTS = EVIDENCE
else:
    EVIDENCE = os.path.join(ROOT, 'docs', 'lab7', 'evidence')
    IMG = os.path.join(EVIDENCE, 'img')
    OUTPUTS = os.path.join(EVIDENCE, 'outputs')
INDEX = os.path.join(EVIDENCE, 'index.json')


def ensure_dirs():
    os.makedirs(IMG, exist_ok=True)
    os.makedirs(OUTPUTS, exist_ok=True)


def register(file, phase, description, source):
    """Agrega la evidencia o reemplaza la que tenga el mismo archivo."""
    ensure_dirs()
    entries = json.load(open(INDEX, encoding='utf-8')) if os.path.exists(INDEX) else []
    entry = {'file': file, 'phase': str(phase), 'description': description, 'source': source,
             'captured_at': datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')}
    entries = [e for e in entries if e['file'] != file] + [entry]
    entries.sort(key=lambda e: e['file'])
    with open(INDEX, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
        f.write('\n')
