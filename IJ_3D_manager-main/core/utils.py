import os
import shutil
import time
from pathlib import Path
from PIL import Image
import customtkinter as ctk
import webbrowser
from core.paths import DATA_DIR, BUNDLE_DIR

BASE_DIR    = DATA_DIR
MEDIA_DIR   = DATA_DIR / "src_media"
INVOICE_DIR = MEDIA_DIR / "invoices"

APP_BG_COLOR  = "#141414"
CARD_BG_COLOR = "#212121"
BORDER_COLOR  = "#333333"
ACCENT_COLOR  = "#00a2ff"

def _ensure_media_dirs():
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    INVOICE_DIR.mkdir(parents=True, exist_ok=True)

def copy_to_media(src_path: str, subfolder: str = "") -> str:
    _ensure_media_dirs()
    dest_dir = MEDIA_DIR / subfolder if subfolder else MEDIA_DIR
    src = Path(src_path)
    filename = src.name

    dest = dest_dir / filename
    if dest.exists():
        filename = f"{src.stem}_{int(time.time())}{src.suffix}"
        dest = dest_dir / filename

    shutil.copy2(src, dest)
    return filename

def resolve_media_path(stored_value: str, subfolder: str = "") -> str | None:
    if not stored_value:
        return None
    if os.path.isabs(stored_value):
        return stored_value
    if subfolder:
        return str(MEDIA_DIR / subfolder / stored_value)
    return str(MEDIA_DIR / stored_value)

IMAGE_CACHE = {}

def load_and_resize_image(path: str | None, size=(150, 150)):
    if not path or not os.path.exists(path):
        return None
        
    cache_key = f"{path}_{size[0]}x{size[1]}"
    if cache_key in IMAGE_CACHE:
        return IMAGE_CACHE[cache_key]
        
    try:
        img = Image.open(path)
        img.thumbnail(size, Image.Resampling.LANCZOS)
        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
        IMAGE_CACHE[cache_key] = ctk_img
        return ctk_img
    except Exception:
        pass
    return None

def open_url(url: str):
    if url:
        webbrowser.open(url)
