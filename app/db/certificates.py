from __future__ import annotations

import random
from typing import Any, Optional

from app.db.base import connect


async def init() -> None:
    conn = await connect("certificates.db")
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            tickets_count INTEGER NOT NULL,
            owner_name TEXT,
            issue_reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'stock',
            created_at TEXT NOT NULL,
            issued_at TEXT,
            redeemed_at TEXT,
            redeemed_session TEXT,
            redeemed_row TEXT,
            redeemed_seats TEXT
        )
        """
    )
    await _ensure_columns(conn)
    await conn.commit()
    await conn.close()


async def _ensure_columns(conn) -> None:
    cur = await conn.execute("PRAGMA table_info(certificates)")
    columns = {row[1] for row in await cur.fetchall()}

    alter_map = {
        "tickets_count": "ALTER TABLE certificates ADD COLUMN tickets_count INTEGER NOT NULL DEFAULT 2",
        "issue_reason": "ALTER TABLE certificates ADD COLUMN issue_reason TEXT NOT NULL DEFAULT 'Не указано'",
        "issued_at": "ALTER TABLE certificates ADD COLUMN issued_at TEXT",
        "redeemed_session": "ALTER TABLE certificates ADD COLUMN redeemed_session TEXT",
        "redeemed_row": "ALTER TABLE certificates ADD COLUMN redeemed_row TEXT",
        "redeemed_seats": "ALTER TABLE certificates ADD COLUMN redeemed_seats TEXT",
    }
    for key, sql in alter_map.items():
        if key not in columns:
            await conn.execute(sql)


async def _code_exists(conn, code: str) -> bool:
    cur = await conn.execute("SELECT 1 FROM certificates WHERE code = ?", (code,))
    return (await cur.fetchone()) is not None


async def generate_unique_code() -> str:
    conn = await connect("certificates.db")
    for _ in range(100):
        code = f"9{random.randint(10_000_000, 99_999_999)}"
        if not await _code_exists(conn, code):
            await conn.close()
            return code
    await conn.close()
    raise RuntimeError("Не удалось сгенерировать уникальный код сертификата")


async def add_certificate(code: str, tickets_count: int, created_at: str) -> None:
    conn = await connect("certificates.db")
    await conn.execute(
        """
        INSERT INTO certificates(code, tickets_count, status, created_at, issue_reason)
        VALUES(?, ?, 'stock', ?, 'Не указано')
        """,
        (code, tickets_count, created_at),
    )
    await conn.commit()
    await conn.close()


async def create_batch(quantity: int, tickets_count: int, created_at: str) -> list[str]:
    codes: list[str] = []
    for _ in range(quantity):
        code = await generate_unique_code()
        await add_certificate(code, tickets_count, created_at)
        codes.append(code)
    return codes


async def get_available(tickets_count: int) -> Optional[dict[str, Any]]:
    conn = await connect("certificates.db")
    cur = await conn.execute(
        """
        SELECT * FROM certificates
        WHERE status='stock' AND tickets_count=?
        ORDER BY created_at ASC, id ASC
        LIMIT 1
        """,
        (tickets_count,),
    )
    row = await cur.fetchone()
    await conn.close()
    return dict(row) if row else None


async def issue_certificate(code: str, owner_name: str, issue_reason: str, issued_at: str) -> bool:
    conn = await connect("certificates.db")
    cur = await conn.execute(
        """
        UPDATE certificates
        SET owner_name=?, issue_reason=?, issued_at=?, status='active'
        WHERE code=? AND status='stock'
        """,
        (owner_name, issue_reason, issued_at, code),
    )
    await conn.commit()
    changed = cur.rowcount > 0
    await conn.close()
    return changed


async def find_by_code_part(code_part: str) -> list[dict[str, Any]]:
    conn = await connect("certificates.db")
    cur = await conn.execute(
        """
        SELECT code, tickets_count, owner_name, issue_reason, status, created_at,
               issued_at,
               redeemed_at, redeemed_session, redeemed_row, redeemed_seats
        FROM certificates
        WHERE code LIKE ?
        ORDER BY created_at DESC
        LIMIT 20
        """,
        (f"%{code_part}%",),
    )
    rows = [dict(r) for r in await cur.fetchall()]
    await conn.close()
    return rows


async def get_by_code(code: str) -> Optional[dict[str, Any]]:
    conn = await connect("certificates.db")
    cur = await conn.execute(
        """
        SELECT code, tickets_count, owner_name, issue_reason, status, created_at,
               issued_at,
               redeemed_at, redeemed_session, redeemed_row, redeemed_seats
        FROM certificates
        WHERE code = ?
        """,
        (code,),
    )
    row = await cur.fetchone()
    await conn.close()
    return dict(row) if row else None


async def redeem(code: str, redeemed_at: str, session: str, row: str, seats: str) -> bool:
    conn = await connect("certificates.db")
    cur = await conn.execute(
        """
        UPDATE certificates
        SET status='redeemed', redeemed_at=?, redeemed_session=?, redeemed_row=?, redeemed_seats=?
        WHERE code=? AND status='active'
        """,
        (redeemed_at, session, row, seats, code),
    )
    await conn.commit()
    changed = cur.rowcount > 0
    await conn.close()
    return changed


async def stats() -> dict[str, Any]:
    conn = await connect("certificates.db")
    cur = await conn.execute(
        """
        SELECT status, tickets_count, COUNT(*) as cnt
        FROM certificates
        GROUP BY status, tickets_count
        """
    )
    rows = await cur.fetchall()
    await conn.close()
    summary: dict[str, Any] = {
        "stock": {},
        "active": {},
        "redeemed": {},
    }
    for row in rows:
        status = row["status"]
        summary.setdefault(status, {})
        summary[status][row["tickets_count"]] = row["cnt"]
    return summary


async def filter_certificates(
    reason: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
) -> list[dict[str, Any]]:
    conn = await connect("certificates.db")
    sql = (
        "SELECT code, tickets_count, owner_name, issue_reason, status, created_at, issued_at, redeemed_at, "
        "redeemed_session, redeemed_row, redeemed_seats "
        "FROM certificates WHERE 1=1"
    )
    params: list[Any] = []
    if reason:
        sql += " AND issue_reason = ?"
        params.append(reason)
    if date_from:
        sql += " AND date(COALESCE(issued_at, created_at)) >= date(?)"
        params.append(date_from)
    if date_to:
        sql += " AND date(COALESCE(issued_at, created_at)) <= date(?)"
        params.append(date_to)

    sql += " ORDER BY created_at DESC LIMIT 50"
    cur = await conn.execute(sql, tuple(params))
    rows = [dict(r) for r in await cur.fetchall()]
    await conn.close()
    return rows
