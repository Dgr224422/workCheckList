from typing import Any
from app.db.base import connect


async def init() -> None:
    conn = await connect("certificates.db")
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            amount INTEGER NOT NULL,
            owner_name TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            owner_name TEXT,
            amount INTEGER NOT NULL,
            issued_at TEXT NOT NULL,
            redeemed_at TEXT
        )
        """
    )
    await conn.commit()
    await conn.close()


async def add_certificate(code: str, amount: int, owner_name: str | None, created_at: str) -> None:
    conn = await connect("certificates.db")
    await conn.execute(
        "INSERT INTO certificates(code, amount, owner_name, created_at) VALUES(?, ?, ?, ?)",
        (code, amount, owner_name, created_at),
    )
    await conn.commit()
    await conn.close()


async def find_by_code_part(code_part: str) -> list[dict[str, Any]]:
    conn = await connect("certificates.db")
    cur = await conn.execute(
        "SELECT code, amount, owner_name, status, created_at, redeemed_at FROM certificates WHERE code LIKE ? ORDER BY created_at DESC LIMIT 10",
async def find_by_code_part(code_part: str) -> list[dict[str, Any]]:
    conn = await connect("certificates.db")
    cur = await conn.execute(
        "SELECT code, owner_name, amount, issued_at, redeemed_at FROM certificates WHERE code LIKE ? ORDER BY code LIMIT 10",
        (f"%{code_part}%",),
    )
    rows = [dict(r) for r in await cur.fetchall()]
    await conn.close()
    return rows


async def get_by_code(code: str) -> dict[str, Any] | None:
    conn = await connect("certificates.db")
    cur = await conn.execute(
        "SELECT code, amount, owner_name, status, created_at, redeemed_at FROM certificates WHERE code = ?",
        (code,),
    )
    row = await cur.fetchone()
    await conn.close()
    return dict(row) if row else None


async def redeem(code: str, redeemed_at: str) -> bool:
    conn = await connect("certificates.db")
    cur = await conn.execute(
        "UPDATE certificates SET status='redeemed', redeemed_at=? WHERE code=? AND status='active'",
        (redeemed_at, code),
    )
    await conn.commit()
    changed = cur.rowcount > 0
    await conn.close()
    return changed
