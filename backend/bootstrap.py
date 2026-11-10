"""
Composition root: el UNICO lugar donde se crean los adaptadores concretos y
se inyectan, por constructor, en los servicios de aplicacion.

    api  ->  application  ->  domain  <-  infrastructure
                  ^                            |
                  +------ bootstrap.py --------+

Los adaptadores no guardan estado por request (usan la sesion de
Flask-SQLAlchemy, que es por request), asi que el contenedor se arma una
vez al crear la app y queda en app.extensions['mecatrack'].
"""

from dataclasses import dataclass

from application.ai_assistant.services import AiAssistantService
from application.catalog.services import (BayService, BusinessService, PartService, ServiceCatalogService,
                                          StaffService, VehicleService)
from application.identity.services import AuthService
from application.market_data.services import MarketDataService
from application.payments.services import PaymentService
from application.scheduling.services import AppointmentService
from application.tracking.services import TrackingService
from domain.scheduling.allocation import ResourceAllocator
from domain.shared.ports import HealthProbe
from infrastructure.analytics.duckdb_analytics import DuckDbMarketAnalytics
from infrastructure.llm.gemini_gateway import GeminiGateway
from infrastructure.market_data.clients import (SOCRATA_BASE, DanePopulationSource, DivipolaSource, RuntFleetSource,
                                                SocrataClient)
from infrastructure.market_data.health import BreakerHealthMonitor
from infrastructure.market_data.snapshot_store import JsonFileSnapshotStore
from infrastructure.persistence.repositories.ai_call_log import SqlAlchemyAiCallLog
from infrastructure.persistence.repositories.appointment_repository import SqlAlchemyAppointmentRepository
from infrastructure.persistence.repositories.bay_repository import SqlAlchemyBayRepository
from infrastructure.persistence.repositories.business_repository import SqlAlchemyBusinessRepository
from infrastructure.persistence.repositories.part_repository import SqlAlchemyPartRepository
from infrastructure.persistence.repositories.payment_repository import SqlAlchemyPaymentRepository
from infrastructure.persistence.repositories.service_repository import SqlAlchemyServiceRepository
from infrastructure.persistence.repositories.service_tracking_repository import SqlAlchemyTrackingRepository
from infrastructure.persistence.repositories.user_repository import SqlAlchemyUserRepository
from infrastructure.persistence.repositories.vehicle_repository import SqlAlchemyVehicleRepository
from infrastructure.persistence.health import SqlAlchemyHealthProbe
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork, SystemClock
from infrastructure.resilience.circuit_breaker import CircuitBreaker
from infrastructure.resilience.http_client import ResilientHttpClient, TransientHttpError
from infrastructure.resilience.retry import RetryPolicy
from infrastructure.security.password_hasher import WerkzeugPasswordHasher

EXTENSION_KEY = 'mecatrack'


@dataclass
class Container:
    auth: AuthService
    business: BusinessService
    staff: StaffService
    bays: BayService
    parts: PartService
    catalog: ServiceCatalogService
    vehicles: VehicleService
    appointments: AppointmentService
    payments: PaymentService
    tracking: TrackingService
    ai_assistant: AiAssistantService
    market_data: MarketDataService
    health: HealthProbe


def build_market_data(config, clock, transport=None):
    """
    Un circuit breaker por dependencia externa (host): si datos.gov.co se
    cae, el geoportal del DANE sigue funcionando y viceversa. Los breakers
    guardan estado, por eso se crean una sola vez con la app.
    """
    policy = RetryPolicy(max_retries=config['MARKET_MAX_RETRIES'], base_delay=config['MARKET_RETRY_BASE_SECONDS'],
                         max_delay=config['MARKET_RETRY_MAX_SECONDS'], retry_on=(TransientHttpError,))

    def http_for(host):
        breaker = CircuitBreaker(host, failure_threshold=config['CIRCUIT_FAILURE_THRESHOLD'],
                                 recovery_timeout=config['CIRCUIT_RECOVERY_SECONDS'],
                                 failure_exceptions=(TransientHttpError,))
        return ResilientHttpClient(breaker, policy, timeout_s=config['MARKET_HTTP_TIMEOUT_SECONDS'],
                                   transport=transport)

    datos_gov = http_for('datos.gov.co')
    dane = http_for('geoportal.dane.gov.co')
    socrata = SocrataClient(datos_gov, base_url=config.get('MARKET_SOCRATA_BASE_URL', SOCRATA_BASE),
                            app_token=config.get('SOCRATA_APP_TOKEN'))
    sources = [RuntFleetSource(socrata), DivipolaSource(socrata), DanePopulationSource(dane)]
    return MarketDataService(sources, JsonFileSnapshotStore(config['MARKET_DATA_DIR']),
                             BreakerHealthMonitor([datos_gov.breaker, dane.breaker]),
                             DuckDbMarketAnalytics(config['MARKET_DATA_DIR']), clock)


def build_container(app):
    uow = SqlAlchemyUnitOfWork()
    clock = SystemClock()

    users = SqlAlchemyUserRepository()
    businesses = SqlAlchemyBusinessRepository()
    bays = SqlAlchemyBayRepository()
    services = SqlAlchemyServiceRepository()
    parts = SqlAlchemyPartRepository()
    vehicles = SqlAlchemyVehicleRepository()
    appointments = SqlAlchemyAppointmentRepository()
    payments = SqlAlchemyPaymentRepository()
    tracking = SqlAlchemyTrackingRepository()

    business = BusinessService(businesses, uow)
    allocator = ResourceAllocator(bays, users, appointments)
    # La configuracion del LLM se lee en cada llamada (las pruebas la cambian).
    llm = GeminiGateway(settings=lambda: app.config)

    return Container(
        auth=AuthService(users, WerkzeugPasswordHasher(), uow),
        business=business,
        staff=StaffService(users, uow),
        bays=BayService(bays, business, uow),
        parts=PartService(parts, business, uow),
        catalog=ServiceCatalogService(services, business, uow),
        vehicles=VehicleService(vehicles, users, uow),
        appointments=AppointmentService(appointments, vehicles, services, allocator, payments, uow),
        payments=PaymentService(payments, appointments, uow, clock),
        tracking=TrackingService(appointments, tracking, parts, uow),
        ai_assistant=AiAssistantService(services, llm, SqlAlchemyAiCallLog(), clock),
        market_data=build_market_data(app.config, clock),
        health=SqlAlchemyHealthProbe(),
    )


def install(app):
    app.extensions[EXTENSION_KEY] = build_container(app)
    return app.extensions[EXTENSION_KEY]
