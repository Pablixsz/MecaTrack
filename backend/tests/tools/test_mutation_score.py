"""scripts/mutation_score.py: el build debe fallar por debajo del minimo."""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / 'scripts' / 'mutation_score.py'
spec = importlib.util.spec_from_file_location('mutation_score', SCRIPT)
mutation_score = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mutation_score)


def stats_file(tmp_path, killed, total):
    path = tmp_path / 'stats.json'
    path.write_text(json.dumps({'killed': killed, 'survived': total - killed, 'no_tests': 0,
                                'timeout': 0, 'total': total}))
    return str(path)


@pytest.mark.parametrize('killed, total, expected', [(0, 0, 0.0), (1, 2, 50.0), (3, 4, 75.0)])
def test_compute_score(killed, total, expected):
    assert mutation_score.compute_score({'killed': killed, 'total': total}) == expected


@pytest.mark.parametrize('killed, exit_code', [(49, 1), (50, 0), (51, 0)])
def test_exit_code_uses_50_percent_as_the_default_minimum(tmp_path, killed, exit_code):
    assert mutation_score.main(['--stats', stats_file(tmp_path, killed, 100)]) == exit_code


def test_minimum_can_be_raised(tmp_path, capsys):
    assert mutation_score.main(['--stats', stats_file(tmp_path, 60, 100), '--min', '61']) == 1
    assert 'mutation score: 60.0% (min 61.0%)' in capsys.readouterr().out
