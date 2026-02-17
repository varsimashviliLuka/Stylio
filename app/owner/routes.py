from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user

from ..extensions import db
from ..models import (
    Salon, Service, Staff, StaffService,
    SalonPhoto, StaffAvailability,
    SalonWorkingHours, SalonSpecialHours
)

from ..utils_uploads import allowed_file, save_image, safe_delete_file
from datetime import datetime, date

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

def get_salon_hours_for_date(salon_id: int, day):
    """
    Returns dict: {"is_closed": bool, "start": "HH:MM"|None, "end": "HH:MM"|None}
    Special day overrides weekly.
    """
    # Special override first
    special = SalonSpecialHours.query.filter_by(salon_id=salon_id, day=day).first()
    if special:
        if special.is_closed:
            return {"is_closed": True, "start": None, "end": None}
        return {"is_closed": False, "start": special.start_time, "end": special.end_time}

    # Weekly schedule fallback
    wd = day.weekday()  # 0=Mon..6=Sun
    weekly = SalonWorkingHours.query.filter_by(salon_id=salon_id, weekday=wd).first()

    if not weekly:
        # default if not configured
        return {"is_closed": False, "start": "09:00", "end": "19:00"}

    if weekly.is_closed:
        return {"is_closed": True, "start": None, "end": None}

    # if row exists but missing times, default
    return {
        "is_closed": False,
        "start": weekly.start_time or "09:00",
        "end": weekly.end_time or "19:00"
    }


@owner_bp.route("/manage-businesses")
@login_required
def manage_businesses():
    owner_required()
    salons = Salon.query.filter_by(owner_user_id=current_user.id).all()

    salon_hours_lines = {}
    salon_special_lines = {}

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    def compress_weekdays(day_list):
        """day_list sorted ints 0..6 -> ['Mon–Fri', 'Sat–Sun'] etc."""
        if not day_list:
            return []

        ranges = []
        start = prev = day_list[0]
        for d in day_list[1:]:
            if d == prev + 1:
                prev = d
            else:
                ranges.append((start, prev))
                start = prev = d
        ranges.append((start, prev))

        out = []
        for a, b in ranges:
            if a == b:
                out.append(day_names[a])
            else:
                out.append(f"{day_names[a]}–{day_names[b]}")
        return out

    for salon in salons:
        # Weekly hours
        weekly_rows = SalonWorkingHours.query.filter_by(salon_id=salon.id).all()
        weekly_map = {r.weekday: r for r in weekly_rows}

        weekly_norm = []
        for wd in range(7):
            r = weekly_map.get(wd)
            if not r:
                weekly_norm.append({"wd": wd, "is_closed": False, "start": "09:00", "end": "19:00"})
            else:
                if r.is_closed:
                    weekly_norm.append({"wd": wd, "is_closed": True, "start": None, "end": None})
                else:
                    weekly_norm.append({
                        "wd": wd,
                        "is_closed": False,
                        "start": r.start_time or "09:00",
                        "end": r.end_time or "19:00"
                    })

        groups = {}
        for x in weekly_norm:
            key = (x["is_closed"], x["start"], x["end"])
            groups.setdefault(key, []).append(x["wd"])

        lines = []
        def group_sort(item):
            (is_closed, start, end), days = item
            return (1 if is_closed else 0, min(days))

        for (is_closed, start, end), days in sorted(groups.items(), key=group_sort):
            day_ranges = compress_weekdays(sorted(days))
            day_label = ", ".join(day_ranges)
            if is_closed:
                lines.append(f"{day_label} Closed")
            else:
                lines.append(f"{day_label} {start}–{end}")

        salon_hours_lines[salon.id] = lines

        # Special days (upcoming) max 3
        specials = (
            SalonSpecialHours.query
            .filter(SalonSpecialHours.salon_id == salon.id, SalonSpecialHours.day >= date.today())
            .order_by(SalonSpecialHours.day.asc())
            .limit(3)
            .all()
        )

        spec_lines = []
        for s in specials:
            if s.is_closed:
                spec_lines.append(f"{s.day} Closed")
            else:
                st = s.start_time or "09:00"
                en = s.end_time or "19:00"
                spec_lines.append(f"{s.day} {st}–{en}")

        salon_special_lines[salon.id] = spec_lines

    return render_template(
        "manage_businesses/manage_businesses.html",
        salons=salons,
        salon_hours_lines=salon_hours_lines,
        salon_special_lines=salon_special_lines
    )


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

        # ✅ Optional: allowlist Google Maps links
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

        # ✅ Optional: allowlist Google Maps links
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

    # ✅ Unavailability grouped by staff_id -> day -> {all_day, times[]}
    availability_rows = (
        StaffAvailability.query
        .join(Staff, StaffAvailability.staff_id == Staff.id)
        .filter(Staff.salon_id == salon.id)
        .order_by(
            StaffAvailability.day.desc(),
            StaffAvailability.time.asc().nullsfirst()
        )
        .all()
    )

    staff_day_blocks = {}
    for a in availability_rows:
        staff_day_blocks.setdefault(a.staff_id, {})
        staff_day_blocks[a.staff_id].setdefault(a.day, {"all_day": False, "times": []})

        if a.time is None or str(a.time).strip() == "":
            staff_day_blocks[a.staff_id][a.day]["all_day"] = True
            staff_day_blocks[a.staff_id][a.day]["times"] = []
        else:
            if not staff_day_blocks[a.staff_id][a.day]["all_day"]:
                staff_day_blocks[a.staff_id][a.day]["times"].append(a.time)

    # normalize
    for sid, daymap in staff_day_blocks.items():
        for d, data in daymap.items():
            data["times"] = sorted(set(data["times"]))

    # ✅ Weekly hours dict: weekday -> {is_closed, start, end}
    weekly_rows = SalonWorkingHours.query.filter_by(salon_id=salon.id).all()
    weekly = {r.weekday: r for r in weekly_rows}

    weekly_hours = {}
    for wd in range(7):
        r = weekly.get(wd)
        weekly_hours[wd] = {
            "is_closed": bool(r.is_closed) if r else False,
            # ✅ default 09:00–19:00
            "start": (r.start_time if r and r.start_time else "09:00"),
            "end": (r.end_time if r and r.end_time else "19:00"),
        }

    # ✅ Special days list (date overrides)
    special_days = (
        SalonSpecialHours.query
        .filter_by(salon_id=salon.id)
        .order_by(SalonSpecialHours.day.desc())
        .all()
    )

    return render_template(
        "manage_businesses/salon_edit.html",
        salon=salon,
        services=services,
        staff=staff,
        staff_day_blocks=staff_day_blocks,
        weekly_hours=weekly_hours,
        special_days=special_days
    )


# =========================
# SALON WORKING HOURS (WEEKLY)
# =========================
@owner_bp.route("/manage-businesses/salon/<int:salon_id>/hours/weekly/save", methods=["POST"])
@login_required
def save_salon_weekly_hours(salon_id):
    owner_required()
    salon = owner_salon_or_404(salon_id)

    # ✅ 08:00–22:00 selectable (you can expand further if you want)
    allowed_times = {
        "08:00","09:00","10:00","11:00","12:00","13:00","14:00","15:00",
        "16:00","17:00","18:00","19:00","20:00","21:00","22:00"
    }

    for wd in range(7):
        closed = request.form.get(f"closed_{wd}") == "on"
        start = (request.form.get(f"start_{wd}") or "").strip()
        end = (request.form.get(f"end_{wd}") or "").strip()

        if not closed:
            if start not in allowed_times or end not in allowed_times:
                flash("Please select valid working times.", "danger")
                return redirect(url_for("owner.edit_salon", salon_id=salon.id))

            # basic order check (string compare works for HH:MM)
            if start >= end:
                flash("Start time must be before end time.", "danger")
                return redirect(url_for("owner.edit_salon", salon_id=salon.id))
        else:
            start = None
            end = None

        row = SalonWorkingHours.query.filter_by(salon_id=salon.id, weekday=wd).first()
        if not row:
            row = SalonWorkingHours(salon_id=salon.id, weekday=wd)
            db.session.add(row)

        row.is_closed = closed
        row.start_time = start
        row.end_time = end

    db.session.commit()
    flash("Weekly working hours saved.", "success")
    return redirect(url_for("owner.edit_salon", salon_id=salon.id))


# =========================
# SALON SPECIAL DAYS (OVERRIDES)
# =========================
@owner_bp.route("/manage-businesses/salon/<int:salon_id>/hours/special/set", methods=["POST"])
@login_required
def set_salon_special_day(salon_id):
    owner_required()
    salon = owner_salon_or_404(salon_id)

    day_str = (request.form.get("day") or "").strip()
    is_closed = request.form.get("is_closed") == "on"
    start = (request.form.get("start") or "").strip()
    end = (request.form.get("end") or "").strip()

    if not day_str:
        flash("Please select a date.", "danger")
        return redirect(url_for("owner.edit_salon", salon_id=salon.id))

    try:
        day = datetime.strptime(day_str, "%Y-%m-%d").date()
    except ValueError:
        flash("Invalid date.", "danger")
        return redirect(url_for("owner.edit_salon", salon_id=salon.id))

    allowed_times = {
        "08:00","09:00","10:00","11:00","12:00","13:00","14:00","15:00",
        "16:00","17:00","18:00","19:00","20:00","21:00","22:00"
    }

    if is_closed:
        start = None
        end = None
    else:
        if start not in allowed_times or end not in allowed_times:
            flash("Please select valid special hours.", "danger")
            return redirect(url_for("owner.edit_salon", salon_id=salon.id))
        if start >= end:
            flash("Special day start time must be before end time.", "danger")
            return redirect(url_for("owner.edit_salon", salon_id=salon.id))

    row = SalonSpecialHours.query.filter_by(salon_id=salon.id, day=day).first()
    if not row:
        row = SalonSpecialHours(salon_id=salon.id, day=day)
        db.session.add(row)

    row.is_closed = is_closed
    row.start_time = start
    row.end_time = end

    db.session.commit()
    flash("Special day saved.", "success")
    return redirect(url_for("owner.edit_salon", salon_id=salon.id))


@owner_bp.route("/manage-businesses/salon/<int:salon_id>/hours/special/<int:special_id>/delete", methods=["POST"])
@login_required
def delete_salon_special_day(salon_id, special_id):
    owner_required()
    salon = owner_salon_or_404(salon_id)

    row = SalonSpecialHours.query.filter_by(id=special_id, salon_id=salon.id).first_or_404()
    db.session.delete(row)
    db.session.commit()

    flash("Special day deleted.", "success")
    return redirect(url_for("owner.edit_salon", salon_id=salon.id))



# =========================
# STAFF UNAVAILABILITY (multi-time per day)
# =========================
@owner_bp.route("/manage-businesses/salon/<int:salon_id>/staff/<int:staff_id>/unavailability/set", methods=["POST"])
@login_required
def set_staff_unavailability(salon_id, staff_id):
    owner_required()
    salon = owner_salon_or_404(salon_id)

    staff = Staff.query.filter_by(id=staff_id, salon_id=salon.id).first_or_404()

    day_str = (request.form.get("day") or "").strip()
    times = request.form.getlist("times")  # multi-select; can be empty => all day

    if not day_str:
        flash("Please select a day.", "danger")
        return redirect(url_for("owner.edit_salon", salon_id=salon.id))

    try:
        day = datetime.strptime(day_str, "%Y-%m-%d").date()
    except ValueError:
        flash("Invalid date.", "danger")
        return redirect(url_for("owner.edit_salon", salon_id=salon.id))

    # ✅ Enforce: date must be a working day (special overrides weekly)
    hours = get_salon_hours_for_date(salon.id, day)
    if hours["is_closed"]:
        flash("This day is CLOSED for the salon. Choose another date.", "danger")
        return redirect(url_for("owner.edit_salon", salon_id=salon.id))

    # ✅ 08:00–22:00 allowed (match your salon hours UI)
    allowed_times = {
        "08:00","09:00","10:00","11:00","12:00","13:00","14:00","15:00",
        "16:00","17:00","18:00","19:00","20:00","21:00","22:00"
    }

    cleaned = []
    for t in times:
        t = (t or "").strip()
        if not t:
            continue

        if t not in allowed_times:
            flash("Invalid time selected.", "danger")
            return redirect(url_for("owner.edit_salon", salon_id=salon.id))

        cleaned.append(t)

    unique_times = sorted(set(cleaned))

    # ✅ Enforce: selected times must fit within salon working hours of that day
    # Rule: start <= time < end
    start = hours["start"] or "09:00"
    end = hours["end"] or "19:00"

    for t in unique_times:
        if not (start <= t < end):
            flash(f"Selected time {t} is outside salon working hours ({start}–{end}).", "danger")
            return redirect(url_for("owner.edit_salon", salon_id=salon.id))

    # ✅ Replace mode: wipe that day entries then insert new ones
    StaffAvailability.query.filter_by(staff_id=staff.id, day=day).delete()
    db.session.commit()

    # Empty list => All day block
    if len(unique_times) == 0:
        db.session.add(StaffAvailability(staff_id=staff.id, day=day, time=None))
    else:
        for t in unique_times:
            db.session.add(StaffAvailability(staff_id=staff.id, day=day, time=t))

    db.session.commit()
    flash("Unavailability saved.", "success")
    return redirect(url_for("owner.edit_salon", salon_id=salon.id))


@owner_bp.route("/manage-businesses/salon/<int:salon_id>/staff/<int:staff_id>/unavailability/<day_str>/clear", methods=["POST"])
@login_required
def clear_staff_unavailability_day(salon_id, staff_id, day_str):
    owner_required()
    salon = owner_salon_or_404(salon_id)

    staff = Staff.query.filter_by(id=staff_id, salon_id=salon.id).first_or_404()

    try:
        day = datetime.strptime(day_str, "%Y-%m-%d").date()
    except ValueError:
        flash("Invalid date.", "danger")
        return redirect(url_for("owner.edit_salon", salon_id=salon.id))

    StaffAvailability.query.filter_by(staff_id=staff.id, day=day).delete()
    db.session.commit()

    flash("Unavailability cleared for that day.", "success")
    return redirect(url_for("owner.edit_salon", salon_id=salon.id))


# =========================
# SERVICES
# =========================
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


# =========================
# STAFF
# =========================
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

    if staff.photo_path:
        try:
            safe_delete_file(
                base_dir=current_app.config["UPLOAD_FOLDER"],
                rel_path=staff.photo_path.replace("uploads/", "", 1)
            )
        except Exception as e:
            print("Failed to delete staff photo file:", e, flush=True)

    db.session.delete(staff)
    db.session.commit()

    flash("Staff deleted.", "success")
    return redirect(url_for("owner.edit_salon", salon_id=salon.id))


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


# =========================
# SALON PHOTOS
# =========================
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

    is_main = (existing_count == 0)

    p = SalonPhoto(salon_id=salon.id, file_path=rel_path, is_main=is_main)
    db.session.add(p)

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

    if was_main:
        next_photo = SalonPhoto.query.filter_by(salon_id=salon.id).order_by(SalonPhoto.id.asc()).first()
        if next_photo:
            SalonPhoto.query.filter_by(salon_id=salon.id).update({"is_main": False})
            next_photo.is_main = True
            db.session.commit()

    flash("Photo deleted.", "success")
    return redirect(url_for("owner.edit_salon", salon_id=salon.id))


# =========================
# STAFF PHOTO UPLOAD/DELETE
# =========================
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

    if staff.photo_path:
        safe_delete_file(current_app.config["UPLOAD_FOLDER"], staff.photo_path.replace("uploads/", "", 1))

    rel_path = save_image(
        file_storage=file,
        base_dir=current_app.config["UPLOAD_FOLDER"],
        subdir=current_app.config["STAFF_UPLOAD_SUBDIR"],
        max_side=1200,
        quality=80
    )

    if rel_path.startswith("staff/") or rel_path.startswith("salons/"):
        staff.photo_path = f"uploads/{rel_path}"
    elif rel_path.startswith("uploads/"):
        staff.photo_path = rel_path
    elif rel_path.startswith("/static/"):
        staff.photo_path = rel_path.replace("/static/", "", 1)
    else:
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
        rel = staff.photo_path.replace("uploads/", "", 1)
        safe_delete_file(current_app.config["UPLOAD_FOLDER"], rel)

        staff.photo_path = None
        db.session.commit()

    flash("Staff photo deleted.", "success")
    return redirect(url_for("owner.edit_salon", salon_id=salon.id))
