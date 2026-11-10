from infrastructure.persistence.extensions import db

class Bay(db.Model):
    __tablename__ = 'bays'

    bay_id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.business_id'), nullable=False)
    bay_number = db.Column(db.String(20), nullable=False)
    has_elevator = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    status = db.Column(db.String(20), nullable=False, default='available', server_default='available')

    business = db.relationship('Business', back_populates='bays')
    appointments = db.relationship('Appointment', back_populates='bay')

    __table_args__ = (
        db.UniqueConstraint('business_id', 'bay_number', name='bays_business_id_bay_number_key'),
        db.CheckConstraint("status IN ('available', 'under_maintenance')", name='check_bay_status'),
    )
