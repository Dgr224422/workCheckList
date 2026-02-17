from pathlib import Path

import aiosqlite

DB_DIR = Path("data")
DB_DIR.mkdir(exist_ok=True)


async def connect(db_name: str) -> aiosqlite.Connection:
    db_path = DB_DIR / db_name
    conn = await aiosqlite.connect(db_path)
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = aiosqlite.Row
    return conn
