from datetime import datetime
from pathlib import Path


MEDIA_DIR = Path("media")
MEDIA_DIR.mkdir(exist_ok=True)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def today_date() -> str:
    return datetime.now().date().isoformat()


def build_media_path(prefix: str, code: str, ext: str = "jpg") -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_code = "".join(ch for ch in code if ch.isalnum() or ch in ("-", "_")) or "file"
    directory = MEDIA_DIR / prefix
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{ts}_{safe_code}.{ext}"
