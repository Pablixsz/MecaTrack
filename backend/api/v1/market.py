"""
/api/v1/market: datos abiertos colombianos (datos.gov.co y DANE) y analisis
con DuckDB para el panel del dueño. Solo traduce HTTP <-> MarketDataService.

Los docstrings son publicos (summary/description de OpenAPI): van en ingles.
"""

from dataclasses import asdict

from flask.views import MethodView
from flask_smorest import Blueprint

from api.auth import role_required
from api.deps import container
from api.v1.schemas.error_schema import FORBIDDEN_EXAMPLE, UNAUTHORIZED_EXAMPLE, ApiErrorSchema, error_example
from api.v1.schemas.market_schema import (CIRCUIT_EXAMPLE, FLEET_AGE_ROW, AnalyticsResultSchema,
                                          RefreshResponseSchema, SourcesResponseSchema)

blp = Blueprint('Market', __name__, description='Colombian open data (datos.gov.co, DANE) analysed with DuckDB, '
                                                'protected by circuit breakers and retries with backoff.')

ROLES = ('owner', 'admin')
NOT_LOADED_EXAMPLE = error_example(
    'market_data_not_loaded',
    'Open data not downloaded yet: runt_fleet. Run POST /api/v1/market/refresh first.',
    {'missing_sources': ['runt_fleet']})


def _error(status, description, example):
    return blp.alt_response(status, schema=ApiErrorSchema, description=description, example=example)


def _auth_errors(func):
    func = _error(401, 'Missing or invalid token. Log in with POST /api/auth/login first.', UNAUTHORIZED_EXAMPLE)(func)
    func = _error(403, 'The token role is not `owner` or `admin`.', FORBIDDEN_EXAMPLE)(func)
    return blp.doc(security=[{'bearerAuth': []}])(func)


def _not_loaded(func):
    return _error(409, 'The open data has not been downloaded yet.', NOT_LOADED_EXAMPLE)(func)


def _circuits():
    return [asdict(h) for h in container().market_data.health()]


@blp.route('/sources')
class Sources(MethodView):

    @role_required(*ROLES)
    @blp.response(200, SourcesResponseSchema, description='Sources, last snapshots and circuit breaker states.',
                  example={'sources': [{'key': 'runt_fleet', 'title': 'Crecimiento del parque automotor RUNT 2.0',
                                        'publisher': 'Ministerio de Transporte (datos.gov.co)',
                                        'url': 'https://www.datos.gov.co/resource/u3vn-bdcy.json',
                                        'fetched_at': '2026-10-25T01:59:11.703291', 'rows': 28007}],
                           'circuits': [CIRCUIT_EXAMPLE]})
    @_auth_errors
    def get(self):
        """List open-data sources and circuit states

        Returns each Colombian open-data source (RUNT vehicle fleet and DIVIPOLA
        from datos.gov.co, CNPV 2018 population from the DANE geoportal) with
        its last downloaded snapshot, plus the state of the circuit breaker
        that protects each external host. Requires an `owner` or `admin` token.
        """
        service = container().market_data
        snapshots = service.snapshots()
        sources = []
        for info in service.sources():
            snapshot = snapshots.get(info.key)
            sources.append({**asdict(info), 'fetched_at': snapshot.fetched_at.isoformat() if snapshot else None,
                            'rows': snapshot.rows if snapshot else None})
        return {'sources': sources, 'circuits': _circuits()}


@blp.route('/refresh')
class Refresh(MethodView):

    @role_required(*ROLES)
    @blp.response(200, RefreshResponseSchema, description='Result per source and circuit states after the refresh.',
                  example={'results': [{'source': 'runt_fleet', 'title': 'Crecimiento del parque automotor RUNT 2.0',
                                        'publisher': 'Ministerio de Transporte (datos.gov.co)',
                                        'url': 'https://www.datos.gov.co/resource/u3vn-bdcy.json', 'ok': True,
                                        'rows': 28007, 'elapsed_ms': 1372, 'error': None, 'circuit_open': False}],
                           'circuits': [CIRCUIT_EXAMPLE]})
    @_auth_errors
    def post(self):
        """Download the open data again

        Calls every source through the resilient HTTP client: transient
        failures (timeouts, connection errors, HTTP 429/5xx) are retried with
        exponential backoff and jitter, and each host has a circuit breaker
        (3 consecutive failures open it for 30 s). A failing source does not
        stop the others and keeps its previous snapshot. Always answers 200;
        check `ok` per source. Requires an `owner` or `admin` token.
        """
        results = container().market_data.refresh()
        return {'results': [asdict(r) for r in results], 'circuits': _circuits()}


def _analytics_doc(example_rows, example_summary):
    def decorate(func):
        func = blp.response(200, AnalyticsResultSchema, description='Columns, rows, summary and the SQL used.',
                            example={'name': '...', 'title': '...', 'description': '...',
                                     'columns': [{'key': 'clase', 'label': 'Clase', 'type': 'text'}],
                                     'rows': example_rows, 'summary': example_summary, 'sql': 'WITH ... SELECT ...',
                                     'elapsed_ms': 89.5, 'snapshots': {'runt_fleet': '2026-10-25T01:59:11.703291'}})(func)
        return _not_loaded(_auth_errors(func))
    return decorate


@blp.route('/analytics/fleet-age')
class FleetAge(MethodView):

    @role_required(*ROLES)
    @_analytics_doc([FLEET_AGE_ROW], {'vehiculos_analizados': 22054289, 'antiguedad_media_ponderada': 13.38,
                                      'excluidos_por_calidad': 8864})
    def get(self):
        """Fleet age by vehicle class

        DuckDB query over the RUNT snapshot: years since registration of the
        active fleet per class (cars, motorcycles, trucks, vans), with
        descriptive statistics weighted by number of vehicles: mean, standard
        deviation, min, P25, median, P75, P90, max and share of vehicles with
        10+ years. Registrations before 1950 are excluded as data errors.
        """
        return asdict(container().market_data.fleet_age())


@blp.route('/analytics/motorization')
class Motorization(MethodView):

    @role_required(*ROLES)
    @_analytics_doc([{'puesto': 21, 'cod_dpto': '11', 'departamento': 'BOGOTÁ, D.C.', 'poblacion_2018': 7181469,
                      'vehiculos': 2777337, 'vehiculos_por_1000_hab': 386.7, 'carros_por_1000_hab': 310.1,
                      'pct_motos': 18.6}],
                    {'departamentos': 33, 'media': 514.8, 'mediana': 446.5, 'desviacion': 343.9,
                     'nacional_por_1000_hab': 499.4})
    def get(self):
        """Motorization by department

        DuckDB join of three open datasets: RUNT active vehicles
        (MinTransporte) and CNPV 2018 population (DANE geoportal), linked by
        the DANE DIVIPOLA codes. Returns vehicles per 1,000 inhabitants per
        department and descriptive statistics across departments (mean,
        median, standard deviation, quartiles, min, max and national ratio).
        """
        return asdict(container().market_data.motorization())


@blp.route('/analytics/age-distribution')
class AgeDistribution(MethodView):

    @role_required(*ROLES)
    @_analytics_doc([{'tipo_taller': 'car', 'rango': '20+', 'vehiculos': 2344330, 'pct_del_tipo': 33.6}],
                    {'rangos': ['0-4', '5-9', '10-14', '15-19', '20+']})
    def get(self):
        """Fleet age distribution

        Share of the active fleet of each MecaTrack vehicle type (car,
        motorcycle, truck, van) in each age range (0-4, 5-9, 10-14, 15-19,
        20+ years since registration). Used by the chart of the owner panel.
        """
        return asdict(container().market_data.age_distribution())
