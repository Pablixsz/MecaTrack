"""Casos de uso de la gestion del negocio (taller, personal, bahias, servicios, repuestos, vehiculos)."""

from application.changes import apply_changes
from domain.catalog.entities import ACTIVE_STATUSES, BAY_STATUSES, Bay, Part, Service, Vehicle
from domain.catalog.ports import (BayRepository, BusinessRepository, PartRepository, ServiceRepository,
                                  VehicleRepository)
from domain.identity.entities import USER_STATUSES
from domain.identity.ports import UserRepository
from domain.shared.errors import Conflict, InvalidInput, NotFound, PermissionDenied, PersistenceConflict
from domain.shared.ports import UnitOfWork

INVALID_ACTIVE_STATUS = "Estado inválido, debe ser 'active' o 'inactive'"


def _ensure_active_status(changes):
    if 'status' in changes and changes['status'] not in ACTIVE_STATUSES:
        raise InvalidInput(INVALID_ACTIVE_STATUS)


class BusinessService:

    def __init__(self, businesses: BusinessRepository, uow: UnitOfWork):
        self._businesses = businesses
        self._uow = uow

    def for_actor(self, actor):
        """
        Taller sobre el que opera el usuario. El owner tiene el suyo; admin y
        mecanico no tienen vinculo en el esquema actual y, como hoy existe un
        solo taller, se les asigna el primero.
        """
        business = self._businesses.get_by_owner(actor.user_id) if actor.role == 'owner' \
            else self._businesses.first()
        if not business:
            raise NotFound('No se encontró un negocio asociado')
        return business

    def get_owned(self, actor):
        business = self._businesses.get_by_owner(actor.user_id)
        if not business:
            raise NotFound('No tienes un negocio registrado')
        return business

    def update_owned(self, actor, changes):
        business = self.get_owned(actor)
        apply_changes(business, changes, ('business_name', 'address', 'business_phone',
                                          'business_registration_number'))
        self._businesses.save(business)
        self._uow.commit()


class StaffService:
    """Mecanicos del taller (las cuentas las crea AuthService.register con rol 'mechanic')."""

    def __init__(self, users: UserRepository, uow: UnitOfWork):
        self._users = users
        self._uow = uow

    def list_mechanics(self):
        return self._users.list_mechanics()

    def update_mechanic(self, user_id, changes):
        """Un mecanico inactivo no puede iniciar sesion ni recibir citas nuevas."""
        mechanic = self._users.get(user_id)
        if not mechanic or mechanic.role != 'mechanic':
            raise NotFound('Mecánico no encontrado')
        if 'status' in changes and changes['status'] not in USER_STATUSES:
            raise InvalidInput(INVALID_ACTIVE_STATUS)
        apply_changes(mechanic, changes, ('status',))
        # Nombre y telefono solo se cambian si llegan con valor (no se borran).
        apply_changes(mechanic, {k: v for k, v in changes.items() if v}, ('first_name', 'last_name', 'phone'))
        self._users.save(mechanic)
        self._uow.commit()


class BayService:

    def __init__(self, bays: BayRepository, business: BusinessService, uow: UnitOfWork):
        self._bays = bays
        self._business = business
        self._uow = uow

    def list_for(self, actor):
        return self._bays.list_by_business(self._business.for_actor(actor).business_id)

    def create(self, actor, bay_number, has_elevator=False):
        business = self._business.for_actor(actor)
        if self._bays.get_by_number(business.business_id, bay_number):
            raise Conflict('Ya existe una bahía con ese número en este negocio')
        bay = self._bays.add(Bay(business_id=business.business_id, bay_number=bay_number,
                                 has_elevator=bool(has_elevator)))
        self._uow.commit()
        return bay

    def update(self, bay_id, changes):
        bay = self._bays.get(bay_id)
        if not bay:
            raise NotFound('Bahía no encontrada')
        if 'status' in changes and changes['status'] not in BAY_STATUSES:
            raise InvalidInput(f'Estado inválido, debe ser uno de: {BAY_STATUSES}')
        if 'has_elevator' in changes:
            bay.has_elevator = bool(changes['has_elevator'])
        apply_changes(bay, changes, ('status',))
        self._bays.save(bay)
        self._uow.commit()


class PartService:

    def __init__(self, parts: PartRepository, business: BusinessService, uow: UnitOfWork):
        self._parts = parts
        self._business = business
        self._uow = uow

    def list_for(self, actor, include_inactive=False):
        # Los inactivos solo los ve la vista de gestion (owner/admin).
        include_inactive = include_inactive and actor.is_manager
        return self._parts.list_by_business(self._business.for_actor(actor).business_id, include_inactive)

    def create(self, actor, part_name, unit_price, stock_quantity=0):
        business = self._business.for_actor(actor)
        part = self._parts.add(Part(business_id=business.business_id, part_name=part_name,
                                    unit_price=unit_price, stock_quantity=stock_quantity))
        self._uow.commit()
        return part

    def update(self, part_id, changes):
        part = self._parts.get(part_id)
        if not part:
            raise NotFound('Repuesto no encontrado')
        _ensure_active_status(changes)
        apply_changes(part, changes, ('part_name', 'unit_price', 'stock_quantity', 'status'))
        self._parts.save(part)
        self._uow.commit()


class ServiceCatalogService:
    """
    Catalogo de servicios. Lo usan dos APIs con contratos distintos:
    - rutas antiguas (/services): mensajes en espanol, DELETE = desactivar.
    - /api/v1/services: mensajes en ingles con code/details, DELETE = borrar
      si no tiene citas (409 si las tiene) y nombres unicos por taller.
    """

    EDITABLE = ('service_name', 'description', 'estimated_duration_minutes', 'base_price', 'status')

    def __init__(self, services: ServiceRepository, business: BusinessService, uow: UnitOfWork):
        self._services = services
        self._business = business
        self._uow = uow

    # --- rutas antiguas ---------------------------------------------------------

    def list_active(self):
        return self._services.list_active()

    def list_for_management(self, actor):
        """Catalogo completo del taller, incluidos los servicios desactivados."""
        return self._services.list_by_business(self._business.for_actor(actor).business_id)

    def create_basic(self, actor, fields):
        business = self._business.for_actor(actor)
        service = self._services.add(Service(business_id=business.business_id, **fields))
        self._uow.commit()
        return service

    def update_basic(self, service_id, changes):
        service = self._services.get(service_id)
        if not service:
            raise NotFound('Servicio no encontrado')
        _ensure_active_status(changes)
        apply_changes(service, changes, self.EDITABLE)
        self._services.save(service)
        self._uow.commit()

    def deactivate(self, service_id):
        """Borrado logico: puede tener citas historicas asociadas por FK."""
        service = self._services.get(service_id)
        if not service:
            raise NotFound('Servicio no encontrado')
        service.status = 'inactive'
        self._services.save(service)
        self._uow.commit()

    # --- /api/v1 ------------------------------------------------------------------

    def list_by_status(self, status=None):
        return self._services.list_by_status(status)

    def get(self, service_id):
        service = self._services.get(service_id)
        if not service:
            raise NotFound(f'Service {service_id} was not found', details={'service_id': service_id})
        return service

    def create(self, actor, data):
        try:
            business = self._business.for_actor(actor)
        except NotFound:
            raise PermissionDenied('Your account is not linked to a workshop', code='business_not_linked') from None
        self._ensure_unique_name(business.business_id, data['service_name'])
        service = self._services.add(Service(business_id=business.business_id, **data))
        self._commit_or_conflict(data['service_name'])
        return service

    def replace(self, service_id, data):
        service = self.get(service_id)
        self._ensure_unique_name(service.business_id, data['service_name'], exclude_id=service_id)
        apply_changes(service, data, self.EDITABLE)
        self._services.save(service)
        self._commit_or_conflict(data['service_name'])
        return service

    def delete(self, service_id):
        self.get(service_id)
        appointments = self._services.count_appointments(service_id)
        if appointments:
            raise Conflict(f'Service {service_id} has {appointments} appointment(s) and cannot be deleted',
                           code='service_has_appointments',
                           details={'service_id': service_id, 'appointments': appointments})
        self._services.delete(service_id)
        self._uow.commit()

    def _ensure_unique_name(self, business_id, service_name, exclude_id=None):
        duplicate = self._services.find_by_name(business_id, service_name, exclude_id)
        if duplicate:
            raise Conflict(f"A service named '{service_name}' already exists", code='duplicate_service_name',
                           details={'service_name': service_name, 'existing_service_id': duplicate.service_id})

    def _commit_or_conflict(self, service_name):
        # La restriccion UNIQUE(business_id, service_name) cubre la carrera entre
        # dos peticiones simultaneas que pasan el chequeo previo.
        try:
            self._uow.commit()
        except PersistenceConflict:
            raise Conflict(f"A service named '{service_name}' already exists", code='duplicate_service_name',
                           details={'service_name': service_name}) from None


class VehicleService:

    EDITABLE = ('brand', 'model', 'year', 'color', 'vehicle_type', 'mileage', 'fuel_type', 'transmission_type')
    CREATE_FIELDS = ('license_plate', 'brand', 'model', 'year', 'color', 'vehicle_type', 'vin',
                     'engine_displacement', 'mileage', 'fuel_type', 'transmission_type')

    def __init__(self, vehicles: VehicleRepository, users: UserRepository, uow: UnitOfWork):
        self._vehicles = vehicles
        self._users = users
        self._uow = uow

    def owner_for(self, actor, client_user_id=None):
        """
        Dueño del vehiculo segun quien actua: el cliente opera sobre lo suyo; en
        recepcion, el administrador o el dueño del taller indican el cliente.
        """
        if not actor.is_manager:
            if client_user_id not in (None, actor.user_id):
                raise PermissionDenied('No puedes operar a nombre de otro cliente')
            return actor.user_id
        if client_user_id is None:
            raise InvalidInput('Indica el cliente (client_user_id)')
        client = self._users.get(client_user_id)
        if not client or client.role != 'client':
            raise NotFound('Cliente no encontrado')
        return client.user_id

    def register(self, actor, data, client_user_id=None):
        owner_user_id = self.owner_for(actor, client_user_id)
        if self._vehicles.get_by_plate(data['license_plate']):
            raise Conflict('Esa placa ya está registrada')
        vehicle = self._vehicles.add(Vehicle(owner_user_id=owner_user_id,
                                             **{f: data.get(f) for f in self.CREATE_FIELDS}))
        self._uow.commit()
        return vehicle

    def list_mine(self, actor, client_user_id=None):
        return self._vehicles.list_by_owner(self.owner_for(actor, client_user_id))

    def get(self, actor, vehicle_id):
        vehicle = self._vehicles.get(vehicle_id)
        if not vehicle:
            raise NotFound('Vehículo no encontrado')
        if actor.is_client and vehicle.owner_user_id != actor.user_id:
            raise PermissionDenied('No tienes permiso para ver este vehículo')
        return vehicle

    def update(self, actor, vehicle_id, changes):
        vehicle = self._owned(actor, vehicle_id, 'No tienes permiso para editar este vehículo')
        apply_changes(vehicle, changes, self.EDITABLE)
        self._vehicles.save(vehicle)
        self._uow.commit()

    def delete(self, actor, vehicle_id):
        self._owned(actor, vehicle_id, 'No tienes permiso para eliminar este vehículo')
        # Las citas historicas referencian al vehiculo por FK: no se puede borrar.
        if self._vehicles.has_appointments(vehicle_id):
            raise Conflict('Este vehículo tiene citas registradas y no se puede eliminar')
        self._vehicles.delete(vehicle_id)
        self._uow.commit()

    def _owned(self, actor, vehicle_id, forbidden_message):
        vehicle = self._vehicles.get(vehicle_id)
        if not vehicle:
            raise NotFound('Vehículo no encontrado')
        if vehicle.owner_user_id != actor.user_id:
            raise PermissionDenied(forbidden_message)
        return vehicle
