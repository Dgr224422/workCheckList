from typing import Any
from app.db.base import connect


async def init() -> None:
    conn = await connect("popcorn.db")
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS popcorn_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_date TEXT NOT NULL,
            bucket_size REAL NOT NULL,
            yesterday_end INTEGER NOT NULL,
            warehouse_morning INTEGER NOT NULL,
            sleeves_taken INTEGER NOT NULL,
            sold_cashier INTEGER NOT NULL,
            tz_left INTEGER NOT NULL,
            warehouse_after_take INTEGER NOT NULL,
            warehouse_after_take INTEGER NOT NULL,
            sold_cashier INTEGER NOT NULL,
            tz_left INTEGER NOT NULL,
            end_of_day INTEGER NOT NULL,
            cashier_expected INTEGER NOT NULL,
            delta INTEGER NOT NULL,
            photo_path TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    await conn.commit()
    await conn.close()


async def add_record(payload: dict[str, Any]) -> None:
    conn = await connect("popcorn.db")
    await conn.execute(
        """
        INSERT INTO popcorn_daily(
            report_date, bucket_size, yesterday_end, warehouse_morning,
            sleeves_taken, sold_cashier, tz_left, warehouse_after_take,
            end_of_day, cashier_expected, delta, photo_path, created_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["report_date"],
            payload["bucket_size"],
            payload["yesterday_end"],
            payload["warehouse_morning"],
            payload["sleeves_taken"],
            payload["sold_cashier"],
            payload["tz_left"],
            payload["warehouse_after_take"],
            payload["end_of_day"],
            payload["cashier_expected"],
            payload["delta"],
            payload["photo_path"],
            payload["created_at"],
        ),
    )
    await conn.commit()
    await conn.close()


async def get_last_end_of_day(bucket_size: float) -> int | None:
    conn = await connect("popcorn.db")
    cur = await conn.execute(
        "SELECT end_of_day FROM popcorn_daily WHERE bucket_size = ? ORDER BY report_date DESC, id DESC LIMIT 1",
        (bucket_size,),
    )
    row = await cur.fetchone()
    await conn.close()
    return int(row["end_of_day"]) if row else None


async def cleanup(keep_days: int) -> int:
    conn = await connect("popcorn.db")
    cur = await conn.execute(
        "DELETE FROM popcorn_daily WHERE date(report_date) < date('now', ?) ",
        (f"-{keep_days} days",),
    )
    await conn.commit()
    count = cur.rowcount
    await conn.close()
    return count


async def report(days: int) -> list[dict[str, Any]]:
    conn = await connect("popcorn.db")
    cur = await conn.execute(
        "SELECT * FROM popcorn_daily WHERE date(report_date) >= date('now', ?) ORDER BY report_date DESC, bucket_size",
        (f"-{days} days",),
    )
    rows = [dict(r) for r in await cur.fetchall()]
    await conn.close()
    return rows
