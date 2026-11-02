"""
Captura de TERMINAL para la Guia 7: ejecuta un comando de verdad, guarda su
stdout/stderr y codigo de salida en docs/lab7/evidence/outputs/ y lo convierte
en PNG con Playwright (Chromium headless). La salida no se edita; solo se puede
recortar con --tail/--head, y en ese caso la imagen lo indica.

    backend/venv/bin/python scripts/evidence/term_capture.py \
        --file 02-pytest-coverage.png --phase 1 --desc "Pruebas y cobertura" \
        --cwd backend --tail 40 -- "venv/bin/python -m pytest -q --cov"

Sale con el mismo codigo del comando, salvo que --expect-exit indique el
esperado (por ejemplo 1 para demostrar un fallo).
"""

import argparse
import os
import subprocess
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'evidencia'))
import evidence_index  # noqa: E402
import render  # noqa: E402


def crop(output, head, tail):
    lines = output.splitlines()
    total = len(lines)
    if tail and total > tail:
        return '\n'.join(lines[-tail:]), f'Salida real recortada: lineas {total - tail + 1}-{total} de {total}.'
    if head and total > head:
        return '\n'.join(lines[:head]), f'Salida real recortada: lineas 1-{head} de {total}.'
    return output, ''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', required=True, help='Nombre del PNG en docs/lab7/evidence/img/')
    parser.add_argument('--phase', required=True)
    parser.add_argument('--desc', required=True)
    parser.add_argument('--cwd', default='.', help='Carpeta de ejecucion, relativa a la raiz del repo')
    parser.add_argument('--display', help='Comando a mostrar si el real lleva rutas largas; nunca cambia lo ejecutado')
    parser.add_argument('--head', type=int)
    parser.add_argument('--tail', type=int)
    parser.add_argument('--expect-exit', type=int)
    parser.add_argument('command')
    args = parser.parse_args()

    cwd = os.path.join(render.ROOT, args.cwd)
    result = subprocess.run(args.command, cwd=cwd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, env={**os.environ, 'COLUMNS': '118'})
    output = result.stdout

    evidence_index.ensure_dirs()
    stem = os.path.splitext(args.file)[0]
    with open(os.path.join(evidence_index.OUTPUTS, f'{stem}.txt'), 'w', encoding='utf-8') as f:
        f.write(f'# {args.command}\n# cwd: {args.cwd} | exit {result.returncode}\n\n{render.strip_ansi(output)}')

    shown, note = crop(output, args.head, args.tail)
    panel = render.terminal_panel(args.display or args.command, f'{shown.rstrip()}\n[exit code: {result.returncode}]', note)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        render.render(browser, os.path.join(evidence_index.IMG, args.file), args.desc,
                      f'MecaTrack · carpeta: {args.cwd}', [panel])
        browser.close()

    evidence_index.register(args.file, args.phase, args.desc, args.command)
    print(f'{args.file}: exit {result.returncode}')
    print(shown[-1500:])
    expected = result.returncode if args.expect_exit is None else args.expect_exit
    sys.exit(0 if result.returncode == expected else (result.returncode or 1))


if __name__ == '__main__':
    main()
