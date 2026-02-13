from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-to-a-random-secret"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///stylio.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "warning"


# -----------------------
# MODELS
# -----------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="customer")  # customer | business_owner

    salons = db.relationship("Salon", backref="owner", lazy=True)

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

    services = db.relationship("Service", backref="salon", cascade="all, delete-orphan", lazy=True)
    staff = db.relationship("Staff", backref="salon", cascade="all, delete-orphan", lazy=True)

    # ✅ Reviews relationship
    reviews = db.relationship("Review", backref="salon", cascade="all, delete-orphan", lazy=True)

    # ✅ Computed fields so Jinja will NEVER crash
    @property
    def review_count(self):
        return len(self.reviews) if self.reviews else 0

    @property
    def average_review(self):
        if not self.reviews:
            return 0
        total = sum(r.rating for r in self.reviews)
        return round(total / len(self.reviews), 1)
    
class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    salon_id = db.Column(db.Integer, db.ForeignKey("salon.id"), nullable=False)

    # optional for now (you can enforce later)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    rating = db.Column(db.Integer, nullable=False)  # 1..5
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())


class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    salon_id = db.Column(db.Integer, db.ForeignKey("salon.id"), nullable=False)

    name = db.Column(db.String(140), nullable=False)
    duration = db.Column(db.Integer, nullable=False, default=60)  # minutes
    price = db.Column(db.Integer, nullable=False, default=0)      # store as integer (USD) for now

    staff_links = db.relationship("StaffService", backref="service", cascade="all, delete-orphan", lazy=True)


class Staff(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    salon_id = db.Column(db.Integer, db.ForeignKey("salon.id"), nullable=False)

    name = db.Column(db.String(140), nullable=False)
    profession = db.Column(db.String(140), nullable=True)
    image = db.Column(db.String(400), nullable=True)

    service_links = db.relationship("StaffService", backref="staff", cascade="all, delete-orphan", lazy=True)


# Many-to-many: staff <-> services
class StaffService(db.Model):
    staff_id = db.Column(db.Integer, db.ForeignKey("staff.id"), primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey("service.id"), primary_key=True)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# -----------------------
# HELPERS
# -----------------------
def owner_required():
    if not current_user.is_authenticated:
        abort(401)
    if current_user.role != "business_owner":
        abort(403)


def owner_salon_or_404(salon_id: int) -> Salon:
    salon = Salon.query.get_or_404(salon_id)
    if salon.owner_user_id != current_user.id:
        abort(403)
    return salon


# -----------------------
# PUBLIC PAGES
# -----------------------
@app.route("/")
def home_page():
    # Show DB salons publicly
    salons = Salon.query.all()
    return render_template("./index/index.html", salons=salons)


@app.route("/book/<int:id>", methods=["GET", "POST"])
def book_a_visit(id):
    salon = Salon.query.get_or_404(id)

    if request.method == "POST":
        data = request.form.to_dict()
        print("BOOKING RECEIVED:", data, flush=True)
        return jsonify({"ok": True, "message": "Booking received"}), 200

    # ✅ Build staff_service_ids mapping: staff.id -> [service_id, ...]
    staff_service_ids = {}
    for st in salon.staff:
        staff_service_ids[st.id] = [link.service_id for link in st.service_links]

    return render_template(
        "./book_a_visit/book_a_visit.html",
        salon=salon,
        staff_service_ids=staff_service_ids
    )

#REVIEWS

@app.route("/salon/<int:salon_id>/review", methods=["POST"])
@login_required
def add_review(salon_id):
    salon = Salon.query.get_or_404(salon_id)

    rating = int(request.form.get("rating", "0") or 0)
    comment = request.form.get("comment", "").strip()

    if rating < 1 or rating > 5:
        return jsonify({"ok": False, "message": "Rating must be 1 to 5"}), 400

    r = Review(
        salon_id=salon.id,
        user_id=current_user.id,
        rating=rating,
        comment=comment
    )
    db.session.add(r)
    db.session.commit()

    return jsonify({
        "ok": True,
        "average_review": salon.average_review,
        "review_count": salon.review_count
    }), 200


# -----------------------
# AUTH
# -----------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "customer")

        if not full_name or not email or not password:
            flash("Please fill all fields.", "danger")
            return redirect(url_for("register"))

        if role not in ["customer", "business_owner"]:
            role = "customer"

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash("Email already exists. Please login.", "warning")
            return redirect(url_for("login"))

        user = User(full_name=full_name, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash("Account created!", "success")
        return redirect(url_for("home_page"))

    return render_template("./auth/register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))

        login_user(user)
        flash("Logged in successfully.", "success")
        return redirect(url_for("home_page"))

    return render_template("./auth/login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "success")
    return redirect(url_for("home_page"))


# -----------------------
# MANAGE BUSINESSES (OWNER)
# -----------------------
@app.route("/manage-businesses")
@login_required
def manage_businesses():
    owner_required()
    salons = Salon.query.filter_by(owner_user_id=current_user.id).all()
    return render_template("./manage_businesses/manage_businesses.html", salons=salons)


@app.route("/manage-businesses/salon/new", methods=["GET", "POST"])
@login_required
def create_salon():
    owner_required()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()

        if not name:
            flash("Salon name is required.", "danger")
            return redirect(url_for("create_salon"))

        salon = Salon(
            owner_user_id=current_user.id,
            name=name,
            location=location,
            description=description
        )
        db.session.add(salon)
        db.session.commit()

        flash("Salon created.", "success")
        return redirect(url_for("edit_salon", salon_id=salon.id))

    return render_template("./manage_businesses/salon_form.html", mode="create", salon=None)


@app.route("/manage-businesses/salon/<int:salon_id>/edit", methods=["GET", "POST"])
@login_required
def edit_salon(salon_id):
    owner_required()
    salon = owner_salon_or_404(salon_id)

    if request.method == "POST":
        salon.name = request.form.get("name", "").strip()
        salon.location = request.form.get("location", "").strip()
        salon.description = request.form.get("description", "").strip()
        db.session.commit()
        flash("Salon updated.", "success")
        return redirect(url_for("edit_salon", salon_id=salon.id))

    services = Service.query.filter_by(salon_id=salon.id).all()
    staff = Staff.query.filter_by(salon_id=salon.id).all()
    return render_template(
        "./manage_businesses/salon_edit.html",
        salon=salon,
        services=services,
        staff=staff
    )


# ---- SERVICES CRUD (inside a salon)
@app.route("/manage-businesses/salon/<int:salon_id>/services/add", methods=["POST"])
@login_required
def add_service(salon_id):
    owner_required()
    salon = owner_salon_or_404(salon_id)

    name = request.form.get("name", "").strip()
    duration = int(request.form.get("duration", "60") or 60)
    price = int(request.form.get("price", "0") or 0)

    if not name:
        flash("Service name required.", "danger")
        return redirect(url_for("edit_salon", salon_id=salon.id))

    s = Service(salon_id=salon.id, name=name, duration=duration, price=price)
    db.session.add(s)
    db.session.commit()
    flash("Service added.", "success")
    return redirect(url_for("edit_salon", salon_id=salon.id))


@app.route("/manage-businesses/salon/<int:salon_id>/services/<int:service_id>/delete", methods=["POST"])
@login_required
def delete_service(salon_id, service_id):
    owner_required()
    salon = owner_salon_or_404(salon_id)

    service = Service.query.get_or_404(service_id)
    if service.salon_id != salon.id:
        abort(403)

    db.session.delete(service)
    db.session.commit()
    flash("Service deleted.", "success")
    return redirect(url_for("edit_salon", salon_id=salon.id))


# ---- STAFF CRUD (inside a salon)
@app.route("/manage-businesses/salon/<int:salon_id>/staff/add", methods=["POST"])
@login_required
def add_staff(salon_id):
    owner_required()
    salon = owner_salon_or_404(salon_id)

    name = request.form.get("name", "").strip()
    profession = request.form.get("profession", "").strip()
    image = request.form.get("image", "").strip()

    if not name:
        flash("Staff name required.", "danger")
        return redirect(url_for("edit_salon", salon_id=salon.id))

    st = Staff(salon_id=salon.id, name=name, profession=profession, image=image)
    db.session.add(st)
    db.session.commit()
    flash("Staff added.", "success")
    return redirect(url_for("edit_salon", salon_id=salon.id))


@app.route("/manage-businesses/salon/<int:salon_id>/staff/<int:staff_id>/delete", methods=["POST"])
@login_required
def delete_staff(salon_id, staff_id):
    owner_required()
    salon = owner_salon_or_404(salon_id)

    staff = Staff.query.get_or_404(staff_id)
    if staff.salon_id != salon.id:
        abort(403)

    db.session.delete(staff)
    db.session.commit()
    flash("Staff deleted.", "success")
    return redirect(url_for("edit_salon", salon_id=salon.id))


# ---- Assign services to staff (skills)
@app.route("/manage-businesses/salon/<int:salon_id>/staff/<int:staff_id>/skills", methods=["GET", "POST"])
@login_required
def staff_skills(salon_id, staff_id):
    owner_required()
    salon = owner_salon_or_404(salon_id)

    staff = Staff.query.get_or_404(staff_id)
    if staff.salon_id != salon.id:
        abort(403)

    services = Service.query.filter_by(salon_id=salon.id).all()

    if request.method == "POST":
        selected_service_ids = request.form.getlist("service_ids")  # list of strings

        # remove all current links
        StaffService.query.filter_by(staff_id=staff.id).delete()
        db.session.commit()

        # add new links
        for sid in selected_service_ids:
            link = StaffService(staff_id=staff.id, service_id=int(sid))
            db.session.add(link)
        db.session.commit()

        flash("Staff skills updated.", "success")
        return redirect(url_for("edit_salon", salon_id=salon.id))

    # current selected
    current_links = StaffService.query.filter_by(staff_id=staff.id).all()
    selected_ids = {l.service_id for l in current_links}

    return render_template(
        "./manage_businesses/staff_skills.html",
        salon=salon,
        staff=staff,
        services=services,
        selected_ids=selected_ids
    )


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
