from infrastructure.persistence.extensions import db

class Vehicle(db.Model):
    __tablename__ = 'vehicles'

    vehicle_id = db.Column(db.Integer, primary_key=True)
    owner_user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    license_plate = db.Column(db.String(10), nullable=False, unique=True)
    brand = db.Column(db.String(50), nullable=False)
    model = db.Column(db.String(50), nullable=False)
    year = db.Column(db.SmallInteger, nullable=False)
    color = db.Column(db.String(30), nullable=True)
    vehicle_type = db.Column(db.String(20), nullable=False)
    vin = db.Column(db.String(17), nullable=True, unique=True)
    engine_displacement = db.Column(db.Numeric(6, 2), nullable=True)
    mileage = db.Column(db.Integer, nullable=True)
    fuel_type = db.Column(db.String(20), nullable=False)
    transmission_type = db.Column(db.String(20), nullable=False)

    owner = db.relationship('User', back_populates='vehicles')
    appointments = db.relationship('Appointment', back_populates='vehicle')

    __table_args__ = (
        db.CheckConstraint("vehicle_type IN ('car', 'motorcycle', 'truck', 'van')", name='check_vehicle_type'),
        db.CheckConstraint("fuel_type IN ('gasoline', 'diesel', 'electric', 'hybrid')", name='check_fuel_type'),
        db.CheckConstraint("transmission_type IN ('manual', 'automatic')", name='check_transmission_type'),
    )
