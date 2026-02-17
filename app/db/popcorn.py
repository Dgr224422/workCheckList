from typing import Any, Optional

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
            end_of_day INTEGER NOT NULL,
            cashier_expected INTEGER NOT NULL,
            delta INTEGER NOT NULL,
            photo_path TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS popcorn_supply (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supply_date TEXT NOT NULL,
            bucket_size REAL NOT NULL,
            quantity INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS popcorn_stock (
            bucket_size REAL PRIMARY KEY,
            quantity INTEGER NOT NULL,
            updated_at TEXT NOT NULL
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


async def get_last_end_of_day(bucket_size: float) -> Optional[int]:
    conn = await connect("popcorn.db")
    cur = await conn.execute(
        "SELECT end_of_day FROM popcorn_daily WHERE bucket_size = ? ORDER BY report_date DESC, id DESC LIMIT 1",
        (bucket_size,),
    )
    row = await cur.fetchone()
    await conn.close()
    return int(row["end_of_day"]) if row else None


async def get_last_report(bucket_size: float) -> Optional[dict[str, Any]]:
    conn = await connect("popcorn.db")
    cur = await conn.execute(
        """
        SELECT end_of_day, created_at
        FROM popcorn_daily
        WHERE bucket_size = ?
        ORDER BY report_date DESC, id DESC
        LIMIT 1
        """,
        (bucket_size,),
    )
    row = await cur.fetchone()
    await conn.close()
    return dict(row) if row else None


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


async def recent_photos(limit: int = 10) -> list[dict[str, Any]]:
    conn = await connect("popcorn.db")
    cur = await conn.execute(
        """
        SELECT id, report_date, bucket_size, photo_path, created_at
        FROM popcorn_daily
        WHERE photo_path IS NOT NULL
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = [dict(r) for r in await cur.fetchall()]
    await conn.close()
    return rows


async def add_supply(payload: dict[str, Any]) -> None:
    conn = await connect("popcorn.db")
    await conn.execute(
        """
        INSERT INTO popcorn_supply(
            supply_date, bucket_size, quantity, created_at
        ) VALUES(?, ?, ?, ?)
        """,
        (
            payload["supply_date"],
            payload["bucket_size"],
            payload["quantity"],
            payload["created_at"],
        ),
    )
    await conn.commit()
    await conn.close()


async def set_stock(bucket_size: float, quantity: int, updated_at: str) -> None:
    conn = await connect("popcorn.db")
    await conn.execute(
        """
        INSERT INTO popcorn_stock(bucket_size, quantity, updated_at)
        VALUES(?, ?, ?)
        ON CONFLICT(bucket_size) DO UPDATE SET
            quantity=excluded.quantity,
            updated_at=excluded.updated_at
        """,
        (bucket_size, quantity, updated_at),
    )
    await conn.commit()
    await conn.close()


async def add_stock(bucket_size: float, delta: int, updated_at: str) -> None:
    conn = await connect("popcorn.db")
    await conn.execute(
        """
        INSERT INTO popcorn_stock(bucket_size, quantity, updated_at)
        VALUES(?, ?, ?)
        ON CONFLICT(bucket_size) DO UPDATE SET
            quantity=popcorn_stock.quantity + excluded.quantity,
            updated_at=excluded.updated_at
        """,
        (bucket_size, delta, updated_at),
    )
    await conn.commit()
    await conn.close()


async def get_stock(bucket_size: float) -> Optional[int]:
    conn = await connect("popcorn.db")
    cur = await conn.execute(
        "SELECT quantity FROM popcorn_stock WHERE bucket_size = ?",
        (bucket_size,),
    )
    row = await cur.fetchone()
    await conn.close()
    return int(row["quantity"]) if row else None


async def get_all_stock() -> list[dict[str, Any]]:
    conn = await connect("popcorn.db")
    cur = await conn.execute(
        "SELECT bucket_size, quantity, updated_at FROM popcorn_stock ORDER BY bucket_size",
    )
    rows = [dict(r) for r in await cur.fetchall()]
    await conn.close()
    return rows


async def supply_total_for_size(bucket_size: float) -> int:
    conn = await connect("popcorn.db")
    cur = await conn.execute(
        "SELECT COALESCE(SUM(quantity), 0) AS total FROM popcorn_supply WHERE bucket_size = ?",
        (bucket_size,),
    )
    row = await cur.fetchone()
    await conn.close()
    return int(row["total"]) if row else 0


async def supply_total_since(bucket_size: float, since_iso: Optional[str]) -> int:
    conn = await connect("popcorn.db")
    if since_iso is None:
        cur = await conn.execute(
            "SELECT COALESCE(SUM(quantity), 0) AS total FROM popcorn_supply WHERE bucket_size = ?",
            (bucket_size,),
        )
    else:
        cur = await conn.execute(
            """
            SELECT COALESCE(SUM(quantity), 0) AS total
            FROM popcorn_supply
            WHERE bucket_size = ? AND created_at > ?
            """,
            (bucket_size, since_iso),
        )
    row = await cur.fetchone()
    await conn.close()
    return int(row["total"]) if row else 0
