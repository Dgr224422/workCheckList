from datetime import date, timedelta
from typing import Any, Optional

from app.db.base import connect


async def init() -> None:
    conn = await connect("posters.db")
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS posters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            release_date TEXT NOT NULL,
            poster_code TEXT NOT NULL UNIQUE,
            arrived_at TEXT NOT NULL,
            arrived_by INTEGER NOT NULL,
            barcode_code TEXT,
            is_hung INTEGER NOT NULL DEFAULT 0,
            hung_at TEXT,
            hung_by INTEGER,
            hung_photo_path TEXT,
            is_taken_off INTEGER NOT NULL DEFAULT 0,
            taken_off_at TEXT,
            taken_off_by INTEGER,
            taken_off_reason TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            deleted_at TEXT,
            deleted_by INTEGER,
            delete_reason TEXT,
            archived_until TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS poster_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            poster_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            days_before INTEGER NOT NULL,
            sent_date TEXT NOT NULL,
            sent_at TEXT NOT NULL,
            UNIQUE(poster_id, user_id, days_before, sent_date),
            FOREIGN KEY(poster_id) REFERENCES posters(id) ON DELETE CASCADE
        )
        """
    )
    await conn.commit()
    await conn.close()


async def add_poster(payload: dict[str, Any]) -> bool:
    conn = await connect("posters.db")
    try:
        await conn.execute(
            """
            INSERT INTO posters(
                title, release_date, poster_code, arrived_at, arrived_by,
                barcode_code, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["title"],
                payload["release_date"],
                payload["poster_code"],
                payload["arrived_at"],
                payload["arrived_by"],
                payload.get("barcode_code"),
                payload["created_at"],
            ),
        )
        await conn.commit()
        return True
    except Exception:
        return False
    finally:
        await conn.close()


async def get_poster_by_id(poster_id: int) -> Optional[dict[str, Any]]:
    conn = await connect("posters.db")
    cur = await conn.execute("SELECT * FROM posters WHERE id = ?", (poster_id,))
    row = await cur.fetchone()
    await conn.close()
    return dict(row) if row else None


async def get_active_by_code(code: str) -> Optional[dict[str, Any]]:
    conn = await connect("posters.db")
    cur = await conn.execute(
        "SELECT * FROM posters WHERE status='active' AND poster_code = ? LIMIT 1",
        (code,),
    )
    row = await cur.fetchone()
    await conn.close()
    return dict(row) if row else None


async def search_candidates(query: str, limit: int = 5) -> list[dict[str, Any]]:
    conn = await connect("posters.db")
    q = query.strip()
    like = f"%{q}%"
    cur = await conn.execute(
        """
        SELECT id, title, release_date, poster_code, arrived_at, is_hung, hung_photo_path,
               is_taken_off, status, deleted_at
        FROM posters
        WHERE status='active'
          AND (poster_code LIKE ? OR title LIKE ? OR COALESCE(barcode_code, '') LIKE ?)
        ORDER BY
            CASE WHEN poster_code = ? THEN 0 ELSE 1 END,
            CASE WHEN title = ? THEN 0 ELSE 1 END,
            release_date ASC,
            id DESC
        LIMIT ?
        """,
        (like, like, like, q, q, limit),
    )
    rows = [dict(r) for r in await cur.fetchall()]
    await conn.close()
    return rows


async def search_by_release_date(release_date_iso: str, limit: int = 10) -> list[dict[str, Any]]:
    conn = await connect("posters.db")
    cur = await conn.execute(
        """
        SELECT id, title, release_date, poster_code, arrived_at, is_hung, hung_photo_path,
               is_taken_off, status, deleted_at
        FROM posters
        WHERE status='active' AND release_date = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (release_date_iso, limit),
    )
    rows = [dict(r) for r in await cur.fetchall()]
    await conn.close()
    return rows


async def mark_hung(poster_id: int, hung_by: int, hung_at: str, hung_photo_path: str) -> bool:
    conn = await connect("posters.db")
    cur = await conn.execute(
        """
        UPDATE posters
        SET is_hung=1, hung_at=?, hung_by=?, hung_photo_path=?
        WHERE id=? AND status='active' AND is_hung=0
        """,
        (hung_at, hung_by, hung_photo_path, poster_id),
    )
    await conn.commit()
    updated = cur.rowcount > 0
    await conn.close()
    return updated


async def mark_taken_off(poster_id: int, taken_off_by: int, taken_off_at: str, reason: str) -> bool:
    conn = await connect("posters.db")
    cur = await conn.execute(
        """
        UPDATE posters
        SET is_taken_off=1, is_hung=0, taken_off_at=?, taken_off_by=?, taken_off_reason=?
        WHERE id=? AND status='active' AND is_hung=1 AND is_taken_off=0
        """,
        (taken_off_at, taken_off_by, reason, poster_id),
    )
    await conn.commit()
    updated = cur.rowcount > 0
    await conn.close()
    return updated


async def soft_delete(poster_id: int, deleted_by: int, deleted_at: str, reason: str, keep_days: int = 365) -> bool:
    archive_until = (date.fromisoformat(deleted_at[:10]) + timedelta(days=keep_days)).isoformat()
    conn = await connect("posters.db")
    cur = await conn.execute(
        """
        UPDATE posters
        SET status='deleted', deleted_at=?, deleted_by=?, delete_reason=?, archived_until=?
        WHERE id=? AND status='active'
        """,
        (deleted_at, deleted_by, reason, archive_until, poster_id),
    )
    await conn.commit()
    updated = cur.rowcount > 0
    await conn.close()
    return updated


async def cleanup_deleted(today_iso: str) -> int:
    conn = await connect("posters.db")
    cur = await conn.execute(
        """
        DELETE FROM posters
        WHERE status='deleted' AND archived_until IS NOT NULL AND date(archived_until) < date(?)
        """,
        (today_iso,),
    )
    await conn.commit()
    count = cur.rowcount
    await conn.close()
    return count


async def due_for_hang(release_date_iso: str) -> list[dict[str, Any]]:
    conn = await connect("posters.db")
    cur = await conn.execute(
        """
        SELECT id, title, poster_code, release_date
        FROM posters
        WHERE status='active' AND is_hung=0 AND is_taken_off=0 AND release_date = ?
        ORDER BY title COLLATE NOCASE ASC
        """,
        (release_date_iso,),
    )
    rows = [dict(r) for r in await cur.fetchall()]
    await conn.close()
    return rows


async def log_notification_if_new(
    poster_id: int,
    user_id: int,
    days_before: int,
    sent_date: str,
    sent_at: str,
) -> bool:
    conn = await connect("posters.db")
    cur = await conn.execute(
        """
        INSERT OR IGNORE INTO poster_notifications(
            poster_id, user_id, days_before, sent_date, sent_at
        ) VALUES(?, ?, ?, ?, ?)
        """,
        (poster_id, user_id, days_before, sent_date, sent_at),
    )
    await conn.commit()
    created = cur.rowcount > 0
    await conn.close()
    return created
