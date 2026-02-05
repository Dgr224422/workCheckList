from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(slots=True)
class Config:
    bot_token: str
    admin_ids: set[int]
    db_path: str



def _parse_admin_ids(raw: str | None) -> set[int]:
    if not raw:
        return set()
    return {int(item.strip()) for item in raw.split(",") if item.strip()}



def load_config() -> Config:
    load_dotenv()
    token = os.getenv("BOT_TOKEN", "")
    if not token:
        raise ValueError("BOT_TOKEN is not set")

    return Config(
        bot_token=token,
        admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS")),
        db_path=os.getenv("DB_PATH", "checklists.db"),
    )
