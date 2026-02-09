from __future__ import annotations

import random
from typing import Any

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
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
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


async def add_certificate(
    code: str,
    tickets_count: int,
    owner_name: str | None,
    issue_reason: str,
    created_at: str,
) -> None:
    conn = await connect("certificates.db")
    await conn.execute(
        """
        INSERT INTO certificates(code, tickets_count, owner_name, issue_reason, created_at)
        VALUES(?, ?, ?, ?, ?)
        """,
        (code, tickets_count, owner_name, issue_reason, created_at),
    )
    await conn.commit()
    await conn.close()


async def find_by_code_part(code_part: str) -> list[dict[str, Any]]:
    conn = await connect("certificates.db")
    cur = await conn.execute(
        """
        SELECT code, tickets_count, owner_name, issue_reason, status, created_at,
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


async def get_by_code(code: str) -> dict[str, Any] | None:
    conn = await connect("certificates.db")
    cur = await conn.execute(
        """
        SELECT code, tickets_count, owner_name, issue_reason, status, created_at,
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


async def filter_certificates(
    reason: str | None,
    date_from: str | None,
    date_to: str | None,
) -> list[dict[str, Any]]:
    conn = await connect("certificates.db")
    sql = (
        "SELECT code, tickets_count, owner_name, issue_reason, status, created_at, redeemed_at, "
        "redeemed_session, redeemed_row, redeemed_seats "
        "FROM certificates WHERE 1=1"
    )
    params: list[Any] = []
    if reason:
        sql += " AND issue_reason = ?"
        params.append(reason)
    if date_from:
        sql += " AND date(created_at) >= date(?)"
        params.append(date_from)
    if date_to:
        sql += " AND date(created_at) <= date(?)"
        params.append(date_to)

    sql += " ORDER BY created_at DESC LIMIT 50"
    cur = await conn.execute(sql, tuple(params))
    rows = [dict(r) for r in await cur.fetchall()]
    await conn.close()
    return rows
