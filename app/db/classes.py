from typing import Any
from app.db.base import connect


async def init() -> None:
    conn = await connect("classes.db")
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS class_visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT NOT NULL,
            school TEXT,
            district TEXT,
            session_info TEXT,
            tickets_count INTEGER NOT NULL,
            seats_rows TEXT,
            cleanliness_rating INTEGER NOT NULL,
            behavior_rating INTEGER NOT NULL,
            extra_info TEXT,
            photo_path TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    await conn.commit()
    await conn.close()


async def add_visit(payload: dict[str, Any]) -> None:
    conn = await connect("classes.db")
    await conn.execute(
        """
        INSERT INTO class_visits(
            phone, school, district, session_info, tickets_count, seats_rows,
            cleanliness_rating, behavior_rating, extra_info, photo_path, created_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["phone"],
            payload.get("school"),
            payload.get("district"),
            payload.get("session_info"),
            payload["tickets_count"],
            payload.get("seats_rows"),
            payload["cleanliness_rating"],
            payload["behavior_rating"],
            payload.get("extra_info"),
            payload.get("photo_path"),
            payload["created_at"],
        ),
    )
    await conn.commit()
    await conn.close()


async def find_by_phone(phone_part: str) -> list[dict[str, Any]]:
    conn = await connect("classes.db")
    cur = await conn.execute(
        "SELECT * FROM class_visits WHERE phone LIKE ? ORDER BY created_at DESC LIMIT 10",
        (f"%{phone_part}%",),
    )
    rows = [dict(r) for r in await cur.fetchall()]
    await conn.close()
    return rows
