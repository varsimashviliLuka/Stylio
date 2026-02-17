from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.sql import func
from sqlalchemy.orm import validates

from sqlalchemy import UniqueConstraint

from .extensions import db


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    # customer | owner
    role = db.Column(db.String(50), nullable=False, default="customer")

    salons = db.relationship("Salon", backref="owner", lazy=True, cascade="all, delete-orphan")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Salon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(200), nullable=True)
    map_link = db.Column(db.String(500), nullable=True)

    services = db.relationship("Service", backref="salon", cascade="all, delete-orphan", lazy=True)
    staff = db.relationship("Staff", backref="salon", cascade="all, delete-orphan", lazy=True)
    reviews = db.relationship("Review", backref="salon", cascade="all, delete-orphan", lazy=True)

    # ✅ NEW: salon photos (up to 5 enforced in routes)
    photos = db.relationship(
        "SalonPhoto",
        backref="salon",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="SalonPhoto.is_main.desc(), SalonPhoto.id.asc()"
    )

    working_hours = db.relationship(
        "SalonWorkingHours",
        cascade="all, delete-orphan",
        lazy=True
    )

    special_hours = db.relationship(
        "SalonSpecialHours",
        cascade="all, delete-orphan",
        lazy=True
    )

    @property
    def review_count(self):
        return len(self.reviews) if self.reviews else 0

    @property
    def average_review(self):
        if not self.reviews:
            return 0
        total = sum(r.rating for r in self.reviews)
        return round(total / len(self.reviews), 1)

    @property
    def main_photo(self):
        """Convenience: returns the main photo object or None."""
        if not self.photos:
            return None
        for p in self.photos:
            if p.is_main:
                return p
        return self.photos[0]  # fallback

class SalonWorkingHours(db.Model):
    __tablename__ = "salon_working_hours"

    id = db.Column(db.Integer, primary_key=True)
    salon_id = db.Column(db.Integer, db.ForeignKey("salon.id"), nullable=False)

    # 0=Mon ... 6=Sun
    weekday = db.Column(db.Integer, nullable=False)

    is_closed = db.Column(db.Boolean, nullable=False, default=False)

    # store as "09:00"
    start_time = db.Column(db.String(5), nullable=True)
    end_time = db.Column(db.String(5), nullable=True)

    __table_args__ = (
        UniqueConstraint("salon_id", "weekday", name="uq_salon_weekday"),
    )


class SalonSpecialHours(db.Model):
    __tablename__ = "salon_special_hours"

    id = db.Column(db.Integer, primary_key=True)
    salon_id = db.Column(db.Integer, db.ForeignKey("salon.id"), nullable=False)

    day = db.Column(db.Date, nullable=False)

    # If closed => start/end are ignored
    is_closed = db.Column(db.Boolean, nullable=False, default=False)
    start_time = db.Column(db.String(5), nullable=True)
    end_time = db.Column(db.String(5), nullable=True)

    __table_args__ = (
        UniqueConstraint("salon_id", "day", name="uq_salon_day"),
    )

class SalonPhoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    salon_id = db.Column(db.Integer, db.ForeignKey("salon.id"), nullable=False)

    # stored relative to: static/uploads/
    # e.g. "salons/123/abcd.webp"
    file_path = db.Column(db.String(500), nullable=False)

    is_main = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, server_default=func.now())

    @validates("file_path")
    def validate_file_path(self, key, value):
        value = (value or "").strip()
        if not value:
            raise ValueError("file_path cannot be empty")
        return value


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    salon_id = db.Column(db.Integer, db.ForeignKey("salon.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    rating = db.Column(db.Integer, nullable=False)  # 1..5
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, server_default=func.now())


class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    salon_id = db.Column(db.Integer, db.ForeignKey("salon.id"), nullable=False)

    name = db.Column(db.String(140), nullable=False)
    duration = db.Column(db.Integer, nullable=False, default=60)
    price = db.Column(db.Integer, nullable=False, default=0)

    staff_links = db.relationship("StaffService", backref="service", cascade="all, delete-orphan", lazy=True)


class Staff(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    salon_id = db.Column(db.Integer, db.ForeignKey("salon.id"), nullable=False)

    name = db.Column(db.String(140), nullable=False)
    profession = db.Column(db.String(140), nullable=True)

    # ✅ NEW: uploaded photo path (recommended)
    # relative to static/uploads/, e.g. "staff/55/photo.webp"
    photo_path = db.Column(db.String(500), nullable=True)

    # (optional) keep old field if you used it for external URLs
    image = db.Column(db.String(400), nullable=True)

    service_links = db.relationship("StaffService", backref="staff", cascade="all, delete-orphan", lazy=True)

    @property
    def display_image(self):
        """Use uploaded photo if exists, else fallback to old image, else None."""
        return self.photo_path or self.image


class StaffService(db.Model):
    staff_id = db.Column(db.Integer, db.ForeignKey("staff.id"), primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey("service.id"), primary_key=True)

class StaffAvailability(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    staff_id = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=False, index=True)

    # required day
    day = db.Column(db.Date, nullable=False, index=True)

    # optional time: if NULL => whole day
    time = db.Column(db.String(10), nullable=True)  # "09:00", "10:00", ...

    created_at = db.Column(db.DateTime, server_default=func.now())

    staff = db.relationship("Staff", backref=db.backref("availability", cascade="all, delete-orphan", lazy=True))

    @property
    def is_all_day(self):
        return self.time is None or str(self.time).strip() == ""
