from typing import Optional

from app.db.base import connect


async def init() -> None:
    conn = await connect("users.db")
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            role TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    await conn.commit()
    await conn.close()


async def set_role(user_id: int, role: str, updated_at: str) -> None:
    conn = await connect("users.db")
    await conn.execute(
        "INSERT INTO users(user_id, role, updated_at) VALUES(?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET role=excluded.role, updated_at=excluded.updated_at",
        (user_id, role, updated_at),
    )
    await conn.commit()
    await conn.close()


async def get_role(user_id: int) -> Optional[str]:
    conn = await connect("users.db")
    cur = await conn.execute("SELECT role FROM users WHERE user_id=?", (user_id,))
    row = await cur.fetchone()
    await conn.close()
    return row["role"] if row else None
