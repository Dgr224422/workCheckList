from typing import Any

from app.db.base import connect


async def init() -> None:
    conn = await connect("schedule.db")
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS shifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_date TEXT NOT NULL,
            worker_name TEXT NOT NULL,
            shift_time TEXT NOT NULL,
            notes TEXT,
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    await conn.commit()
    await conn.close()


async def add_shift(payload: dict[str, Any]) -> None:
    conn = await connect("schedule.db")
    await conn.execute(
        """
        INSERT INTO shifts(work_date, worker_name, shift_time, notes, created_by, created_at)
        VALUES(?, ?, ?, ?, ?, ?)
        """,
        (
            payload["work_date"],
            payload["worker_name"],
            payload["shift_time"],
            payload.get("notes"),
            payload["created_by"],
            payload["created_at"],
        ),
    )
    await conn.commit()
    await conn.close()


async def month_schedule(year_month: str) -> list[dict[str, Any]]:
    conn = await connect("schedule.db")
    cur = await conn.execute(
        """
        SELECT work_date, worker_name, shift_time, notes, created_by, created_at
        FROM shifts
        WHERE work_date LIKE ?
        ORDER BY work_date, worker_name
        """,
        (f"{year_month}-%",),
    )
    rows = [dict(r) for r in await cur.fetchall()]
    await conn.close()
    return rows
