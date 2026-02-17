from typing import Any

from app.db.base import connect


async def init() -> None:
    conn = await connect("classes.db")
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS classes_visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT NOT NULL,
            tickets_count INTEGER NOT NULL,
            cleanliness_rating INTEGER NOT NULL,
            behavior_rating INTEGER NOT NULL,
            school TEXT,
            district TEXT,
            session_info TEXT,
            seats_rows TEXT,
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
        INSERT INTO classes_visits(
            phone, tickets_count, cleanliness_rating, behavior_rating,
            school, district, session_info, seats_rows,
            extra_info, photo_path, created_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["phone"],
            payload["tickets_count"],
            payload["cleanliness_rating"],
            payload["behavior_rating"],
            payload.get("school"),
            payload.get("district"),
            payload.get("session_info"),
            payload.get("seats_rows"),
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
        """
        SELECT phone, tickets_count, cleanliness_rating, behavior_rating, school,
               district, session_info, seats_rows, extra_info, photo_path, created_at
        FROM classes_visits
        WHERE phone LIKE ?
        ORDER BY created_at DESC
        LIMIT 20
        """,
        (f"%{phone_part}%",),
    )
    rows = [dict(r) for r in await cur.fetchall()]
    await conn.close()
    return rows
