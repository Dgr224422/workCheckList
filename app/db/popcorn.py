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
