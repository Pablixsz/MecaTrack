"""
DuckDbMarketAnalytics sobre snapshots construidos con las respuestas REALES
grabadas (AMAZONAS y BOGOTA D.C.; 3 clases). Sin red ni PostgreSQL.

Los resultados se comparan con calculos independientes en Python y con la
expansion "una fila por vehiculo" + quantile_disc de DuckDB.
"""

import duckdb
import pytest

from bootstrap import build_market_data
from domain.market_data.errors import SnapshotMissing
from infrastructure.analytics import queries
from infrastructure.analytics.duckdb_analytics import DuckDbMarketAnalytics
from infrastructure.persistence.unit_of_work import SystemClock
from tests.market_fixtures import fixture_transport, load

CONFIG = {'MARKET_MAX_RETRIES': 0, 'MARKET_RETRY_BASE_SECONDS': 0, 'MARKET_RETRY_MAX_SECONDS': 0,
          'CIRCUIT_FAILURE_THRESHOLD': 3, 'CIRCUIT_RECOVERY_SECONDS': 30, 'MARKET_HTTP_TIMEOUT_SECONDS': 5}


@pytest.fixture
def analytics(tmp_path):
    service = build_market_data({**CONFIG, 'MARKET_DATA_DIR': str(tmp_path)}, SystemClock(),
                                transport=fixture_transport())
    assert all(r.ok for r in service.refresh())
    return DuckDbMarketAnalytics(str(tmp_path))


def runt_rows(min_year=queries.MIN_REGISTRATION_YEAR):
    return [r for r in load('runt_fleet_sample.json') if int(r['fecha_de_registro']) >= min_year]


def test_missing_snapshots_raise_a_domain_error(tmp_path):
    with pytest.raises(SnapshotMissing) as error:
        DuckDbMarketAnalytics(str(tmp_path)).fleet_age_by_class()
    assert error.value.code == 'market_data_not_loaded' and 'runt_fleet' in error.value.details['missing_sources']


def test_fleet_age_totals_and_weighted_mean_match_python(analytics):
    result = analytics.fleet_age_by_class()
    by_class = {r['clase']: r for r in result.rows}
    assert set(by_class) == {'AUTOMOVIL', 'MOTOCICLETA', 'CAMIONETA'}

    for clase, row in by_class.items():
        data = [(2026 - int(r['fecha_de_registro']), int(r['vehiculos'])) for r in runt_rows()
                if r['nombre_de_la_clase'] == clase]
        total = sum(n for _, n in data)
        assert row['vehiculos'] == total
        assert row['media'] == round(sum(age * n for age, n in data) / total, 2)
        assert row['minimo'] == min(a for a, _ in data) and row['maximo'] == max(a for a, _ in data)

    excluded = sum(int(r['vehiculos']) for r in load('runt_fleet_sample.json') if int(r['fecha_de_registro']) < 1950)
    assert result.summary['excluidos_por_calidad'] == excluded
    assert result.sql.startswith('WITH clases_taller') and result.snapshots['runt_fleet']


def test_weighted_percentiles_equal_duckdb_on_one_row_per_vehicle(analytics):
    """Los percentiles por frecuencia acumulada = quantile_disc sobre los datos expandidos."""
    result = {r['clase']: r for r in analytics.fleet_age_by_class().rows}
    con, _ = analytics._connect(['runt'])
    expanded = con.execute(f"""
        WITH {queries.WORKSHOP_CLASSES}, {queries.RUNT_CLEAN}
        SELECT clase, round(stddev_pop(anio_corte - anio_registro), 2),
               quantile_disc(anio_corte - anio_registro, [0.25, 0.5, 0.75, 0.9])
        FROM runt_limpio, range(vehiculos) GROUP BY clase""").fetchall()
    con.close()
    for clase, stddev, (p25, p50, p75, p90) in expanded:
        row = result[clase]
        assert (row['desviacion'], row['p25'], row['mediana'], row['p75'], row['p90']) == (stddev, p25, p50, p75, p90)


def test_motorization_joins_runt_and_dane_through_divipola(analytics):
    result = analytics.motorization_by_department()
    rows = {r['cod_dpto']: r for r in result.rows}
    population = {}
    for f in load('dane_population_sample.json')['features']:
        population[f['attributes']['DPTO_CCDGO']] = population.get(f['attributes']['DPTO_CCDGO'], 0) + \
            f['attributes']['CL0_TT_PERSN']

    # "BOGOTA D.C." (RUNT) se une con "BOGOTÁ, D.C." (DIVIPOLA) pese a la coma y la tilde
    for cod, runt_name in (('11', 'BOGOTA D.C.'), ('91', 'AMAZONAS')):
        vehicles = sum(int(r['vehiculos']) for r in runt_rows() if r['nombre_departamento'] == runt_name)
        assert rows[cod]['vehiculos'] == vehicles
        assert rows[cod]['poblacion_2018'] == population[cod]
        assert rows[cod]['vehiculos_por_1000_hab'] == round(1000 * vehicles / population[cod], 1)

    total = sum(r['vehiculos'] for r in result.rows)
    assert total == sum(int(r['vehiculos']) for r in runt_rows())  # ni se pierden ni se duplican
    assert result.summary['departamentos'] == 2 and result.summary['con_datos'] == 2
    assert [r['puesto'] for r in result.rows] == [1, 2]


def test_san_andres_prefix_match_and_short_keys_are_not_prefix_matched(tmp_path):
    """Regla del cruce por nombre, probada con datos minimos escritos a mano."""
    import json
    snap = lambda records: {'source': 'x', 'fetched_at': '2030-01-01T00:00:00', 'rows': len(records), 'records': records}
    runt = [{'nombre_departamento': d, 'nombre_de_la_clase': 'AUTOMOVIL', 'fecha_de_registro': '2020',
             'vehiculos': '10', 'mes_publicacion': 'OCTUBRE', 'anio_publicacion': '2026'}
            for d in ('ARCHIPIELAGO DE SAN ANDRES, PROVIDENCIA', 'META')]
    divipola = [{'cod_dpto': '88', 'dpto': 'ARCHIPIÉLAGO DE SAN ANDRÉS, PROVIDENCIA Y SANTA CATALINA',
                 'cod_mpio': '88001', 'nom_mpio': 'SAN ANDRÉS', 'tipo_municipio': 'Municipio'},
                {'cod_dpto': '50', 'dpto': 'META', 'cod_mpio': '50001', 'nom_mpio': 'VILLAVICENCIO',
                 'tipo_municipio': 'Municipio'},
                {'cod_dpto': '97', 'dpto': 'METALANDIA', 'cod_mpio': '97001', 'nom_mpio': 'X', 'tipo_municipio': 'Municipio'}]
    population = [{'cod_dpto': c, 'cod_mpio': c + '001', 'municipio': 'x', 'poblacion': 1000} for c in ('88', '50', '97')]
    for name, records in (('runt_fleet', runt), ('divipola', divipola), ('dane_population', population)):
        (tmp_path / f'{name}.json').write_text(json.dumps(snap(records)), encoding='utf-8')

    rows = {r['cod_dpto']: r['vehiculos'] for r in DuckDbMarketAnalytics(str(tmp_path)).motorization_by_department().rows}
    assert rows == {'88': 10, '50': 10, '97': 0}  # 'META' (clave corta) no se pega a 'METALANDIA'


def test_age_distribution_percentages_add_up_to_100(analytics):
    result = analytics.age_distribution()
    for tipo in {r['tipo_taller'] for r in result.rows}:
        assert sum(r['pct_del_tipo'] for r in result.rows if r['tipo_taller'] == tipo) == pytest.approx(100, abs=0.3)
    assert [r['rango'] for r in result.rows if r['tipo_taller'] == 'car'] == ['0-4', '5-9', '10-14', '15-19', '20+']


def test_duckdb_version_is_pinned():
    assert duckdb.__version__ == '2.0.0'
