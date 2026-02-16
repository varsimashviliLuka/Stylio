from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from ..extensions import db
from ..models import Salon, Service, Staff, StaffService

from flask import current_app
from ..utils_uploads import allowed_file, save_image, safe_delete_file
from ..models import SalonPhoto


owner_bp = Blueprint("owner", __name__, url_prefix="/owner")


def owner_required():
    if not current_user.is_authenticated:
        abort(401)
    if current_user.role != "owner":
        abort(403)


def owner_salon_or_404(salon_id: int) -> Salon:
    salon = Salon.query.get_or_404(salon_id)
    if salon.owner_user_id != current_user.id:
        abort(403)
    return salon


@owner_bp.route("/manage-businesses")
@login_required
def manage_businesses():
    owner_required()
    salons = Salon.query.filter_by(owner_user_id=current_user.id).all()
    return render_template("manage_businesses/manage_businesses.html", salons=salons)


@owner_bp.route("/manage-businesses/salon/new", methods=["GET", "POST"])
@login_required
def create_salon():
    owner_required()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        location = request.form.get("location", "").strip()
        map_link = request.form.get("map_link", "").strip()
        description = request.form.get("description", "").strip()

        if not name:
            flash("Salon name is required.", "danger")
            return redirect(url_for("owner.create_salon"))

        # ✅ Optional: basic allowlist so only Google Maps links are saved
        if map_link:
            allowed_prefixes = (
                "https://maps.app.goo.gl/",
                "https://www.google.com/maps",
                "https://goo.gl/maps",
            )
            if not map_link.startswith(allowed_prefixes):
                flash("Please paste a valid Google Maps link.", "danger")
                return redirect(url_for("owner.create_salon"))

        salon = Salon(
            owner_user_id=current_user.id,
            name=name,
            location=location,
            map_link=map_link or None,
            description=description
        )
        db.session.add(salon)
        db.session.commit()

        flash("Salon created.", "success")
        return redirect(url_for("owner.edit_salon", salon_id=salon.id))

    return render_template("manage_businesses/salon_form.html", mode="create", salon=None)


@owner_bp.route("/manage-businesses/salon/<int:salon_id>/edit", methods=["GET", "POST"])
@login_required
def edit_salon(salon_id):
    owner_required()
    salon = owner_salon_or_404(salon_id)

    if request.method == "POST":
        salon.name = request.form.get("name", "").strip()
        salon.location = request.form.get("location", "").strip()
        salon.map_link = request.form.get("map_link", "").strip() or None
        salon.description = request.form.get("description", "").strip()

        # ✅ Optional: basic allowlist so only Google Maps links are saved
        if salon.map_link:
            allowed_prefixes = (
                "https://maps.app.goo.gl/",
                "https://www.google.com/maps",
                "https://goo.gl/maps",
            )
            if not salon.map_link.startswith(allowed_prefixes):
                flash("Please paste a valid Google Maps link.", "danger")
                return redirect(url_for("owner.edit_salon", salon_id=salon.id))

        db.session.commit()
        flash("Salon updated.", "success")
        return redirect(url_for("owner.edit_salon", salon_id=salon.id))

    services = Service.query.filter_by(salon_id=salon.id).all()
    staff = Staff.query.filter_by(salon_id=salon.id).all()

    return render_template(
        "manage_businesses/salon_edit.html",
        salon=salon,
        services=services,
        staff=staff
    )


# SERVICES
@owner_bp.route("/manage-businesses/salon/<int:salon_id>/services/add", methods=["POST"])
@login_required
def add_service(salon_id):
    owner_required()
    salon = owner_salon_or_404(salon_id)

    name = request.form.get("name", "").strip()
    duration = int(request.form.get("duration", "60") or 60)
    price = int(request.form.get("price", "0") or 0)

    if not name:
        flash("Service name required.", "danger")
        return redirect(url_for("owner.edit_salon", salon_id=salon.id))

    s = Service(salon_id=salon.id, name=name, duration=duration, price=price)
    db.session.add(s)
    db.session.commit()
    flash("Service added.", "success")
    return redirect(url_for("owner.edit_salon", salon_id=salon.id))


@owner_bp.route("/manage-businesses/salon/<int:salon_id>/services/<int:service_id>/delete", methods=["POST"])
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
    return redirect(url_for("owner.edit_salon", salon_id=salon.id))


# STAFF
@owner_bp.route("/manage-businesses/salon/<int:salon_id>/staff/add", methods=["POST"])
@login_required
def add_staff(salon_id):
    owner_required()
    salon = owner_salon_or_404(salon_id)

    name = request.form.get("name", "").strip()
    profession = request.form.get("profession", "").strip()
    image = request.form.get("image", "").strip()

    if not name:
        flash("Staff name required.", "danger")
        return redirect(url_for("owner.edit_salon", salon_id=salon.id))

    st = Staff(salon_id=salon.id, name=name, profession=profession, image=image)
    db.session.add(st)
    db.session.commit()
    flash("Staff added.", "success")
    return redirect(url_for("owner.edit_salon", salon_id=salon.id))


@owner_bp.route("/manage-businesses/salon/<int:salon_id>/staff/<int:staff_id>/delete", methods=["POST"])
@login_required
def delete_staff(salon_id, staff_id):
    owner_required()
    salon = owner_salon_or_404(salon_id)

    staff = Staff.query.get_or_404(staff_id)
    if staff.salon_id != salon.id:
        abort(403)

    # ✅ Delete uploaded photo file from disk first
    if staff.photo_path:
        try:
            # photo_path is stored like: "uploads/staff/xxx.webp"
            safe_delete_file(
                base_dir=current_app.config["UPLOAD_FOLDER"],  # should point to static/uploads
                rel_path=staff.photo_path.replace("uploads/", "", 1)
            )
        except Exception as e:
            print("Failed to delete staff photo file:", e, flush=True)

    # ✅ Then delete database record
    db.session.delete(staff)
    db.session.commit()

    flash("Staff deleted.", "success")
    return redirect(url_for("owner.edit_salon", salon_id=salon.id))


# Assign services to staff
@owner_bp.route("/manage-businesses/salon/<int:salon_id>/staff/<int:staff_id>/skills", methods=["GET", "POST"])
@login_required
def staff_skills(salon_id, staff_id):
    owner_required()
    salon = owner_salon_or_404(salon_id)

    staff = Staff.query.get_or_404(staff_id)
    if staff.salon_id != salon.id:
        abort(403)

    services = Service.query.filter_by(salon_id=salon.id).all()

    if request.method == "POST":
        selected_service_ids = request.form.getlist("service_ids")

        StaffService.query.filter_by(staff_id=staff.id).delete()
        db.session.commit()

        for sid in selected_service_ids:
            db.session.add(StaffService(staff_id=staff.id, service_id=int(sid)))

        db.session.commit()
        flash("Staff skills updated.", "success")
        return redirect(url_for("owner.edit_salon", salon_id=salon.id))

    current_links = StaffService.query.filter_by(staff_id=staff.id).all()
    selected_ids = {l.service_id for l in current_links}

    return render_template(
        "manage_businesses/staff_skills.html",
        salon=salon,
        staff=staff,
        services=services,
        selected_ids=selected_ids
    )

@owner_bp.route("/manage-businesses/salon/<int:salon_id>/photos/upload", methods=["POST"])
@login_required
def upload_salon_photo(salon_id):
    owner_required()
    salon = owner_salon_or_404(salon_id)

    file = request.files.get("photo")
    if not file or not file.filename:
        flash("Please choose a photo.", "danger")
        return redirect(url_for("owner.edit_salon", salon_id=salon.id))

    if not allowed_file(file.filename):
        flash("Allowed formats: jpg, jpeg, png, webp.", "danger")
        return redirect(url_for("owner.edit_salon", salon_id=salon.id))

    # max 5 photos per salon
    existing_count = SalonPhoto.query.filter_by(salon_id=salon.id).count()
    if existing_count >= 5:
        flash("Max 5 photos per salon.", "warning")
        return redirect(url_for("owner.edit_salon", salon_id=salon.id))

    rel_path = save_image(
        file_storage=file,
        base_dir=current_app.config["UPLOAD_FOLDER"],
        subdir=current_app.config["SALON_UPLOAD_SUBDIR"],
        max_side=1600,
        quality=80
    )

    # first photo becomes main automatically
    is_main = (existing_count == 0)

    # ✅ FIX: remove sort_order (model doesn't have it)
    p = SalonPhoto(salon_id=salon.id, file_path=rel_path, is_main=is_main)
    db.session.add(p)

    # ✅ FIX: if we set new photo as main, unset others safely
    if is_main:
        SalonPhoto.query.filter_by(salon_id=salon.id).update({"is_main": False})
        p.is_main = True

    db.session.commit()

    flash("Photo uploaded.", "success")
    return redirect(url_for("owner.edit_salon", salon_id=salon.id))


@owner_bp.route("/manage-businesses/salon/<int:salon_id>/photos/<int:photo_id>/main", methods=["POST"])
@login_required
def set_main_salon_photo(salon_id, photo_id):
    owner_required()
    salon = owner_salon_or_404(salon_id)

    photo = SalonPhoto.query.get_or_404(photo_id)
    if photo.salon_id != salon.id:
        abort(403)

    # unset others
    SalonPhoto.query.filter_by(salon_id=salon.id).update({"is_main": False})
    photo.is_main = True
    db.session.commit()

    flash("Main photo updated.", "success")
    return redirect(url_for("owner.edit_salon", salon_id=salon.id))

@owner_bp.route("/manage-businesses/salon/<int:salon_id>/photos/<int:photo_id>/delete", methods=["POST"])
@login_required
def delete_salon_photo(salon_id, photo_id):
    owner_required()
    salon = owner_salon_or_404(salon_id)

    photo = SalonPhoto.query.get_or_404(photo_id)
    if photo.salon_id != salon.id:
        abort(403)

    rel_path = photo.file_path
    was_main = photo.is_main

    db.session.delete(photo)
    db.session.commit()

    safe_delete_file(current_app.config["UPLOAD_FOLDER"], rel_path)

    # if deleted main photo, set another as main (first available)
    if was_main:
        next_photo = SalonPhoto.query.filter_by(salon_id=salon.id).order_by(SalonPhoto.id.asc()).first()
        if next_photo:
            SalonPhoto.query.filter_by(salon_id=salon.id).update({"is_main": False})
            next_photo.is_main = True
            db.session.commit()

    flash("Photo deleted.", "success")
    return redirect(url_for("owner.edit_salon", salon_id=salon.id))

@owner_bp.route("/manage-businesses/salon/<int:salon_id>/staff/<int:staff_id>/photo/upload", methods=["POST"])
@login_required
def upload_staff_photo(salon_id, staff_id):
    owner_required()
    salon = owner_salon_or_404(salon_id)

    staff = Staff.query.get_or_404(staff_id)
    if staff.salon_id != salon.id:
        abort(403)

    file = request.files.get("photo")
    if not file or not file.filename:
        flash("Please choose a photo.", "danger")
        return redirect(url_for("owner.edit_salon", salon_id=salon.id))

    if not allowed_file(file.filename):
        flash("Allowed formats: jpg, jpeg, png, webp.", "danger")
        return redirect(url_for("owner.edit_salon", salon_id=salon.id))

    # delete old uploaded photo file (optional, but recommended)
    if staff.photo_path:
        safe_delete_file(current_app.config["UPLOAD_FOLDER"], staff.photo_path.replace("uploads/", "", 1))

    # Save file to static/uploads/staff/...
    # IMPORTANT: your save_image currently returns "staff/xxx.webp" (not including "uploads/")
    rel_path = save_image(
        file_storage=file,
        base_dir=current_app.config["UPLOAD_FOLDER"],    # should be ".../static/uploads"
        subdir=current_app.config["STAFF_UPLOAD_SUBDIR"],# should be "staff"
        max_side=1200,
        quality=80
    )

    # ✅ Store path relative to /static
    # If save_image returns "staff/..", convert to "uploads/staff/.."
    if rel_path.startswith("staff/") or rel_path.startswith("salons/"):
        staff.photo_path = f"uploads/{rel_path}"
    elif rel_path.startswith("uploads/"):
        staff.photo_path = rel_path
    elif rel_path.startswith("/static/"):
        staff.photo_path = rel_path.replace("/static/", "", 1)
    else:
        # last-resort: assume it should be inside uploads/
        staff.photo_path = f"uploads/{rel_path.lstrip('/')}"

    db.session.commit()
    flash("Staff photo uploaded.", "success")
    print("Saved staff.photo_path =", staff.photo_path, flush=True)

    return redirect(url_for("owner.edit_salon", salon_id=salon.id))


@owner_bp.route("/manage-businesses/salon/<int:salon_id>/staff/<int:staff_id>/photo/delete", methods=["POST"])
@login_required
def delete_staff_photo(salon_id, staff_id):
    owner_required()
    salon = owner_salon_or_404(salon_id)

    staff = Staff.query.get_or_404(staff_id)
    if staff.salon_id != salon.id:
        abort(403)

    if staff.photo_path:
        # your UPLOAD_FOLDER points to ".../static/uploads"
        # safe_delete_file expects rel like "staff/xxx.webp" relative to base_dir
        rel = staff.photo_path.replace("uploads/", "", 1)
        safe_delete_file(current_app.config["UPLOAD_FOLDER"], rel)

        staff.photo_path = None
        db.session.commit()

    flash("Staff photo deleted.", "success")
    return redirect(url_for("owner.edit_salon", salon_id=salon.id))
