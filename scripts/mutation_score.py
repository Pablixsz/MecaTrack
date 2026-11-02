"""
Score de mutation testing: killed / total, a partir de `mutmut export-cicd-stats`.
Sale con codigo 1 si el score queda por debajo del minimo (50 % por defecto).

    cd backend && mutmut run; mutmut export-cicd-stats
    python ../scripts/mutation_score.py [--min 50] [--stats mutants/mutmut-cicd-stats.json]
"""

import argparse
import json
import sys

DEFAULT_MIN_SCORE = 50.0
DEFAULT_STATS = 'mutants/mutmut-cicd-stats.json'


def compute_score(stats):
    """Sin mutantes no hay nada medido: cuenta como 0 para que el build no pase en falso."""
    total = stats['total']
    return 100.0 * stats['killed'] / total if total else 0.0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--min', type=float, default=DEFAULT_MIN_SCORE)
    parser.add_argument('--stats', default=DEFAULT_STATS)
    args = parser.parse_args(argv)

    with open(args.stats, encoding='utf-8') as f:
        stats = json.load(f)

    score = compute_score(stats)
    print(f"killed={stats['killed']} survived={stats['survived']} no_tests={stats['no_tests']} "
          f"timeout={stats['timeout']} total={stats['total']}")
    print(f'mutation score: {score:.1f}% (min {args.min:.1f}%)')
    if score < args.min:
        print('FAIL: mutation score below the minimum')
        return 1
    print('OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
