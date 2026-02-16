from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from ..extensions import db
from ..models import Salon, Review

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home_page():
    salons = Salon.query.all()
    return render_template("index/index.html", salons=salons)


@main_bp.route("/book/<int:id>", methods=["GET", "POST"])
def book_a_visit(id):
    salon = Salon.query.get_or_404(id)

    if request.method == "POST":
        data = request.form.to_dict()
        print("BOOKING RECEIVED:", data, flush=True)
        return jsonify({"ok": True, "message": "Booking received"}), 200

    # staff.id -> [service_id,...]
    staff_service_ids = {}
    for st in salon.staff:
        staff_service_ids[st.id] = [link.service_id for link in st.service_links]

    return render_template(
        "book_a_visit/book_a_visit.html",
        salon=salon,
        staff_service_ids=staff_service_ids
    )


@main_bp.route("/salon/<int:salon_id>/review", methods=["POST"])
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
