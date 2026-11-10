from infrastructure.persistence.extensions import db
from datetime import datetime

class Appointment(db.Model):
    __tablename__ = 'appointments'

    appointment_id = db.Column(db.Integer, primary_key=True)
    client_user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.vehicle_id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('services.service_id'), nullable=False)
    bay_id = db.Column(db.Integer, db.ForeignKey('bays.bay_id'), nullable=False)
    mechanic_user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    scheduled_start = db.Column(db.DateTime, nullable=False)
    scheduled_end = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending', server_default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, server_default=db.func.current_timestamp())

    # Doble FK hacia users: alias explicitos 'client' y 'mechanic'.
    client = db.relationship('User', foreign_keys=[client_user_id], back_populates='client_appointments')
    mechanic = db.relationship('User', foreign_keys=[mechanic_user_id], back_populates='mechanic_appointments')
    vehicle = db.relationship('Vehicle', back_populates='appointments')
    service = db.relationship('Service', back_populates='appointments')
    bay = db.relationship('Bay', back_populates='appointments')
    payments = db.relationship('Payment', back_populates='appointment', order_by='Payment.payment_id')
    tracking_records = db.relationship(
        'ServiceTracking', back_populates='appointment', order_by='ServiceTracking.recorded_at'
    )

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('pending', 'confirmed', 'in_progress', 'completed', 'cancelled')",
            name='check_appointment_status'
        ),
        # Indices para el motor de agendamiento (busqueda de solapamientos por
        # bahia y por mecanico) y para el listado de citas del cliente.
        db.Index('ix_appointments_bay_schedule', 'bay_id', 'scheduled_start', 'scheduled_end'),
        db.Index('ix_appointments_mechanic_schedule', 'mechanic_user_id', 'scheduled_start', 'scheduled_end'),
        db.Index('ix_appointments_client_user_id', 'client_user_id'),
    )
