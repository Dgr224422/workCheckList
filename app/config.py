from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    system_admin_id: int



def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "")
    admin_id = int(os.getenv("SYSTEM_ADMIN_ID", "0"))
    if not token:
        raise RuntimeError("BOT_TOKEN is required")
    if admin_id <= 0:
        raise RuntimeError("SYSTEM_ADMIN_ID must be a positive integer")
    return Settings(bot_token=token, system_admin_id=admin_id)
