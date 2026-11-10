from infrastructure.persistence.extensions import db
from datetime import datetime

class Payment(db.Model):
    __tablename__ = 'payments'

    payment_id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.appointment_id'), nullable=False, index=True)
    payment_type = db.Column(db.String(20), nullable=False)
    payment_method = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending', server_default='pending')
    paid_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, server_default=db.func.current_timestamp())

    appointment = db.relationship('Appointment', back_populates='payments')

    __table_args__ = (
        db.CheckConstraint("payment_type IN ('deposit', 'balance')", name='check_payment_type'),
        db.CheckConstraint("payment_method IN ('cash', 'card', 'transfer')", name='check_payment_method'),
        db.CheckConstraint("status IN ('pending', 'completed', 'failed', 'refunded')", name='check_payment_status'),
    )
