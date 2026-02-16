import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-to-a-random-secret")

    # DB
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'stylio.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Uploads (stored in: app/static/uploads/)
    UPLOAD_FOLDER = os.environ.get(
        "UPLOAD_FOLDER",
        str(BASE_DIR / "app" / "static" / "uploads")
    )
    SALON_UPLOAD_SUBDIR = "salons"
    STAFF_UPLOAD_SUBDIR = "staff"

    # Security / limits
    MAX_CONTENT_LENGTH = 4 * 1024 * 1024  # 4MB max upload (adjust if needed)

    # Optional: restrict file types (your helper will use this too)
    ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
