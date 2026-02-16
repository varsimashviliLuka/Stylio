import os
import uuid
from werkzeug.utils import secure_filename

try:
    from PIL import Image
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

def allowed_file(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS

def save_image(file_storage, base_dir: str, subdir: str, max_side: int = 1600, quality: int = 80) -> str:
    """
    Saves image into base_dir/subdir.
    Returns relative path like: 'salons/abc.webp'
    If Pillow is available -> resize + convert to WEBP for storage savings.
    """
    filename = secure_filename(file_storage.filename or "")
    ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""
    new_name = f"{uuid.uuid4().hex}.{ext if ext else 'jpg'}"

    abs_folder = os.path.join(base_dir, subdir)
    os.makedirs(abs_folder, exist_ok=True)

    abs_path_original = os.path.join(abs_folder, new_name)
    file_storage.save(abs_path_original)

    # If no Pillow, keep as-is
    if not PIL_AVAILABLE:
        return f"{subdir}/{new_name}"

    # Convert to WEBP + resize for big savings
    try:
        img = Image.open(abs_path_original)
        img = img.convert("RGB")

        w, h = img.size
        scale = min(max_side / max(w, h), 1.0)
        if scale < 1.0:
            img = img.resize((int(w * scale), int(h * scale)))

        webp_name = f"{uuid.uuid4().hex}.webp"
        abs_path_webp = os.path.join(abs_folder, webp_name)

        img.save(abs_path_webp, "WEBP", quality=quality, method=6)

        # delete original
        try:
            os.remove(abs_path_original)
        except Exception:
            pass

        return f"{subdir}/{webp_name}"
    except Exception:
        # fallback: keep original if processing fails
        return f"{subdir}/{new_name}"

def safe_delete_file(base_dir: str, rel_path: str) -> None:
    """
    Deletes a file safely only if it's inside base_dir.
    rel_path should be like 'salons/xxx.webp' or 'staff/yyy.webp'
    """
    if not rel_path:
        return
    abs_path = os.path.abspath(os.path.join(base_dir, rel_path))
    abs_base = os.path.abspath(base_dir)

    if not abs_path.startswith(abs_base):
        return  # safety: never delete outside uploads folder

    if os.path.exists(abs_path):
        os.remove(abs_path)
