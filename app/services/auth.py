from app.config import AppContext
from app.db import users

ROLES_ORDER = {"guest": 0, "worker": 1, "admin": 2, "system_admin": 3}


async def get_role(user_id: int, ctx: AppContext) -> str:
    if user_id == ctx.settings.system_admin_id:
        return "system_admin"
    role = await users.get_role(user_id)
    if role:
        return role
    if user_id in ctx.admin_ids:
        return "admin"
    return "guest"


async def ensure_min_role(user_id: int, required: str, ctx: AppContext) -> bool:
    role = await get_role(user_id, ctx)
    return ROLES_ORDER.get(role, 0) >= ROLES_ORDER.get(required, 0)
