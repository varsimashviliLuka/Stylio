from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from datetime import date, datetime

from ..extensions import db

from ..models import (
    Salon, Service, Staff, StaffService,
    SalonPhoto, StaffAvailability,
    SalonWorkingHours, SalonSpecialHours
)


main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home_page():
    salons = Salon.query.all()

    # Build compact hours lines per salon for cards
    salon_hours_lines = {}
    salon_special_lines = {}

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    def compress_weekdays(day_list):
        """day_list is sorted ints 0..6. Return ranges like 'Mon–Fri' or 'Sat–Sun' or 'Tue'."""
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
        # Weekly rows (fallback defaults if not present)
        weekly_rows = SalonWorkingHours.query.filter_by(salon_id=salon.id).all()
        weekly_map = {r.weekday: r for r in weekly_rows}

        # normalize 7 days -> dict entries
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

        # Group by (is_closed, start, end)
        groups = {}
        for x in weekly_norm:
            key = (x["is_closed"], x["start"], x["end"])
            groups.setdefault(key, []).append(x["wd"])

        # Produce display lines
        lines = []
        # Sort groups so open groups first then closed groups, and earlier weekdays first
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

        # Special days: show upcoming (today and forward) max 3
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
        "index/index.html",
        salons=salons,
        salon_hours_lines=salon_hours_lines,
        salon_special_lines=salon_special_lines
    )


@main_bp.route("/book/<int:id>", methods=["GET", "POST"])
def book_a_visit(id):
    salon = Salon.query.get_or_404(id)

    if request.method == "POST":
        data = request.form.to_dict()
        # TODO create booking
        print("BOOKING RECEIVED:", data, flush=True)
        return jsonify({"ok": True, "message": "Booking received"}), 200

    # staff.id -> [service_id,...]
    staff_service_ids = {}
    for st in salon.staff:
        staff_service_ids[st.id] = [link.service_id for link in st.service_links]

    # ✅ weekly_hours dict: wd -> {is_closed,start,end}
    weekly_rows = SalonWorkingHours.query.filter_by(salon_id=salon.id).all()
    weekly_hours = {}
    for r in weekly_rows:
        weekly_hours[int(r.weekday)] = {
            "is_closed": bool(r.is_closed),
            "start": r.start_time or "09:00",
            "end": r.end_time or "19:00",
        }

    # ✅ special days dict: "YYYY-MM-DD" -> {is_closed,start,end}
    special_rows = SalonSpecialHours.query.filter_by(salon_id=salon.id).all()
    special_days = {}
    for s in special_rows:
        key = s.day.strftime("%Y-%m-%d")
        special_days[key] = {
            "is_closed": bool(s.is_closed),
            "start": s.start_time or "09:00",
            "end": s.end_time or "19:00",
        }

    # ✅ staff unavailability dict: staff_id -> day_str -> {all_day, times[]}
    availability_rows = (
        StaffAvailability.query
        .join(Staff, StaffAvailability.staff_id == Staff.id)
        .filter(Staff.salon_id == salon.id)
        .all()
    )

    staff_day_blocks = {}
    for a in availability_rows:
        sid = int(a.staff_id)
        day_str = a.day.strftime("%Y-%m-%d")
        staff_day_blocks.setdefault(sid, {})
        staff_day_blocks[sid].setdefault(day_str, {"all_day": False, "times": []})

        if a.time is None or str(a.time).strip() == "":
            staff_day_blocks[sid][day_str]["all_day"] = True
            staff_day_blocks[sid][day_str]["times"] = []
        else:
            if not staff_day_blocks[sid][day_str]["all_day"]:
                staff_day_blocks[sid][day_str]["times"].append(str(a.time))

    # normalize unique/sorted
    for sid, days in staff_day_blocks.items():
        for d, info in days.items():
            info["times"] = sorted(set(info["times"]))

    # =========================================================
    # ✅ Working hours preview lines (same format as MAIN PAGE)
    #   salon_hours_lines[salon.id] = ["Mon–Fri 09:00–19:00", ...]
    #   salon_special_lines[salon.id] = ["2026-02-20 10:00–15:00", ...]
    # =========================================================
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

    # Weekly normalize (defaults if missing)
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
                    "end": r.end_time or "19:00",
                })

    # Group days by same schedule
    groups = {}
    for x in weekly_norm:
        key = (x["is_closed"], x["start"], x["end"])
        groups.setdefault(key, []).append(x["wd"])

    def group_sort(item):
        (is_closed, start, end), days = item
        return (1 if is_closed else 0, min(days))

    hours_lines = []
    for (is_closed, start, end), days in sorted(groups.items(), key=group_sort):
        day_ranges = compress_weekdays(sorted(days))
        day_label = ", ".join(day_ranges)

        if is_closed:
            hours_lines.append(f"{day_label} Closed")
        else:
            hours_lines.append(f"{day_label} {start}–{end}")

    salon_hours_lines = {salon.id: hours_lines}

    # Upcoming special days (max 3)
    upcoming_specials = (
        SalonSpecialHours.query
        .filter(SalonSpecialHours.salon_id == salon.id, SalonSpecialHours.day >= date.today())
        .order_by(SalonSpecialHours.day.asc())
        .limit(3)
        .all()
    )

    spec_lines = []
    for s in upcoming_specials:
        if s.is_closed:
            spec_lines.append(f"{s.day} Closed")
        else:
            st = s.start_time or "09:00"
            en = s.end_time or "19:00"
            spec_lines.append(f"{s.day} {st}–{en}")

    salon_special_lines = {salon.id: spec_lines}

    return render_template(
        "book_a_visit/book_a_visit.html",
        salon=salon,
        staff_service_ids=staff_service_ids,

        # ✅ data for your booking JS
        weekly_hours=weekly_hours,
        special_days=special_days,
        staff_day_blocks=staff_day_blocks,

        # ✅ data for top card UI (same as index)
        salon_hours_lines=salon_hours_lines,
        salon_special_lines=salon_special_lines,
    )


@main_bp.route("/salon/<int:salon_id>/review", methods=["POST"])

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
