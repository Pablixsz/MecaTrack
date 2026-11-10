"""
Adaptador del puerto MarketAnalytics con DuckDB (base analitica embebida).

Cada consulta abre una conexion en memoria, registra los snapshots JSON como
vistas con read_json y ejecuta SQL analitico. Es barato (milisegundos), no
comparte estado entre hilos de Flask y no deja archivos de base de datos.
"""

import json
import os
import time

import duckdb

from domain.market_data.errors import SnapshotMissing
from domain.market_data.ports import AnalyticsResult, MarketAnalytics
from infrastructure.analytics import queries

SOURCES = {'runt': 'runt_fleet', 'divipola': 'divipola', 'poblacion': 'dane_population'}


def _literal(text):
    """Literal SQL con comillas escapadas. CREATE VIEW no admite parametros preparados;
    el path sale de la configuracion (MARKET_DATA_DIR), nunca del usuario."""
    return "'" + text.replace("'", "''") + "'"


def _column(key, label, kind='number'):
    return {'key': key, 'label': label, 'type': kind}


class DuckDbMarketAnalytics(MarketAnalytics):

    def __init__(self, data_dir):
        self.data_dir = data_dir

    # --- infraestructura de consulta ---------------------------------------------------

    def _paths(self, views):
        paths = {view: os.path.join(self.data_dir, f'{SOURCES[view]}.json') for view in views}
        missing = [SOURCES[view] for view, path in paths.items() if not os.path.exists(path)]
        if missing:
            raise SnapshotMissing(missing)
        return paths

    def _connect(self, views):
        con = duckdb.connect(':memory:')
        snapshots = {}
        for view, path in self._paths(views).items():
            # El snapshot es {"source", "fetched_at", "rows", "records": [...]}; unnest(records)
            # convierte el arreglo JSON en filas con una columna por campo.
            con.execute(f"""CREATE VIEW {view} AS
                            SELECT unnest(records, recursive := true)
                            FROM read_json({_literal(path)}, maximum_object_size = 268435456)""")  # view name from the fixed SOURCES map, path escaped by _literal()  # nosec B608
            snapshots[SOURCES[view]] = con.execute(
                'SELECT fetched_at FROM read_json(?, maximum_object_size = 268435456)', [path]).fetchone()[0]
        return con, snapshots

    @staticmethod
    def _rows(relation):
        columns = [d[0] for d in relation.description]
        return [dict(zip(columns, (float(v) if hasattr(v, 'is_finite') else v for v in row), strict=True))
                for row in relation.fetchall()]

    def _run(self, views, sql):
        con, snapshots = self._connect(views)
        try:
            started = time.perf_counter()
            rows = self._rows(con.execute(sql))
            elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            return con, rows, elapsed_ms, {k: str(v) for k, v in snapshots.items()}
        except Exception:
            con.close()
            raise

    # --- consultas ----------------------------------------------------------------------------

    def fleet_age_by_class(self):
        con, rows, elapsed_ms, snapshots = self._run(['runt'], queries.FLEET_AGE_BY_CLASS)
        try:
            excluded = con.execute(queries.EXCLUDED_BY_QUALITY).fetchone()[0]
            cutoff = con.execute('SELECT max(CAST(anio_publicacion AS INTEGER)), max(mes_publicacion) FROM runt').fetchone()
        finally:
            con.close()
        total = sum(r['vehiculos'] for r in rows)
        weighted_mean = round(sum(r['media'] * r['vehiculos'] for r in rows) / total, 2) if total else None
        return AnalyticsResult(
            name='fleet_age_by_class',
            title='Antigüedad del parque automotor activo por clase',
            description='Años desde el registro (corte RUNT {} {}), ponderado por número de vehículos.'.format(
                cutoff[1], cutoff[0]),
            columns=[_column('clase', 'Clase', 'text'), _column('tipo_taller', 'Tipo MecaTrack', 'text'),
                     _column('vehiculos', 'Vehículos'), _column('media', 'Media'),
                     _column('desviacion', 'Desv. estándar'), _column('minimo', 'Mín.'), _column('p25', 'P25'),
                     _column('mediana', 'Mediana'), _column('p75', 'P75'), _column('p90', 'P90'),
                     _column('maximo', 'Máx.'), _column('pct_10_anios_o_mas', '% con 10+ años')],
            rows=rows,
            summary={'vehiculos_analizados': total, 'antiguedad_media_ponderada': weighted_mean,
                     'excluidos_por_calidad': excluded, 'anio_minimo_valido': queries.MIN_REGISTRATION_YEAR,
                     'corte_runt': f'{cutoff[1]} {cutoff[0]}'},
            sql=queries.FLEET_AGE_BY_CLASS.strip(), elapsed_ms=elapsed_ms, snapshots=snapshots)

    def motorization_by_department(self):
        con, rows, elapsed_ms, snapshots = self._run(['runt', 'divipola', 'poblacion'],
                                                     queries.MOTORIZATION_BY_DEPARTMENT)
        try:
            con.execute(f'CREATE TEMP TABLE motorizacion AS {queries.MOTORIZATION_BY_DEPARTMENT}')
            relation = con.execute(queries.MOTORIZATION_SUMMARY)
            summary = self._rows(relation)[0]
        finally:
            con.close()
        summary['sin_vehiculos_en_runt'] = [r['departamento'] for r in rows if not r['vehiculos']]
        return AnalyticsResult(
            name='motorization_by_department',
            title='Motorización por departamento',
            description='Vehículos activos de las clases que atiende el taller (RUNT, MinTransporte) por cada '
                        '1.000 habitantes censados (CNPV 2018, DANE). Indicativo: RUNT ubica el vehículo en el '
                        'organismo de tránsito donde está matriculado.',
            columns=[_column('puesto', '#'), _column('departamento', 'Departamento', 'text'),
                     _column('poblacion_2018', 'Población 2018'), _column('vehiculos', 'Vehículos'),
                     _column('vehiculos_por_1000_hab', 'Vehículos / 1.000 hab.'),
                     _column('carros_por_1000_hab', 'Carros / 1.000 hab.'), _column('pct_motos', '% motos')],
            rows=rows, summary=summary,
            sql=queries.MOTORIZATION_BY_DEPARTMENT.strip() + '\n\n-- Resumen entre departamentos\n'
                + queries.MOTORIZATION_SUMMARY.strip(),
            elapsed_ms=elapsed_ms, snapshots=snapshots)

    def age_distribution(self):
        con, rows, elapsed_ms, snapshots = self._run(['runt'], queries.AGE_DISTRIBUTION)
        con.close()
        return AnalyticsResult(
            name='age_distribution',
            title='Distribución del parque por rango de antigüedad',
            description='Porcentaje de vehículos de cada tipo MecaTrack en cada rango de años desde el registro.',
            columns=[_column('tipo_taller', 'Tipo', 'text'), _column('rango', 'Años', 'text'),
                     _column('vehiculos', 'Vehículos'), _column('pct_del_tipo', '% del tipo')],
            rows=rows, summary={'rangos': ['0-4', '5-9', '10-14', '15-19', '20+']},
            sql=queries.AGE_DISTRIBUTION.strip(), elapsed_ms=elapsed_ms, snapshots=snapshots)


def dump(result):
    """Ayuda para depurar desde la consola."""
    return json.dumps(result.__dict__, ensure_ascii=False, indent=1, default=str)
