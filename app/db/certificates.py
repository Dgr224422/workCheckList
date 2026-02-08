from typing import Any
from app.db.base import connect


async def init() -> None:
    conn = await connect("certificates.db")
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            owner_name TEXT,
            amount INTEGER NOT NULL,
            issued_at TEXT NOT NULL,
            redeemed_at TEXT
        )
        """
    )
    await conn.commit()
    await conn.close()


async def find_by_code_part(code_part: str) -> list[dict[str, Any]]:
    conn = await connect("certificates.db")
    cur = await conn.execute(
        "SELECT code, owner_name, amount, issued_at, redeemed_at FROM certificates WHERE code LIKE ? ORDER BY code LIMIT 10",
        (f"%{code_part}%",),
    )
    rows = [dict(r) for r in await cur.fetchall()]
    await conn.close()
    return rows
