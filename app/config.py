from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()


def _parse_ids(value: str) -> set[int]:
    ids: set[int] = set()
    if not value.strip():
        return ids
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        ids.add(int(part))
    return ids


@dataclass(frozen=True)
class Settings:
    bot_token: str
    system_admin_id: int
    cleanup_days: int


@dataclass(frozen=True)
class AppContext:
    settings: Settings
    admin_ids: set[int]



def load_context() -> AppContext:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is required")

    system_admin_id = int(os.getenv("SYSTEM_ADMIN_ID", "0"))
    if system_admin_id <= 0:
        raise RuntimeError("SYSTEM_ADMIN_ID must be a positive integer")

    cleanup_days = int(os.getenv("CLEANUP_DAYS", "45"))
    if cleanup_days < 7:
        raise RuntimeError("CLEANUP_DAYS must be >= 7")

    admin_ids = _parse_ids(os.getenv("ADMIN_IDS", ""))
    admin_ids.add(system_admin_id)

    return AppContext(
        settings=Settings(
            bot_token=token,
            system_admin_id=system_admin_id,
            cleanup_days=cleanup_days,
        ),
        admin_ids=admin_ids,
    )
