from __future__ import annotations

from typing import Any, Optional

from app.db.base import connect


async def init() -> None:
    conn = await connect("faq.db")
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS faq_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            created_by INTEGER NOT NULL
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS faq_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            step_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            photo_path TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(article_id) REFERENCES faq_articles(id) ON DELETE CASCADE
        )
        """
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_faq_steps_article ON faq_steps(article_id, step_index)"
    )
    await conn.commit()
    await conn.close()


async def create_article(title: str, created_by: int, created_at: str) -> int:
    conn = await connect("faq.db")
    cur = await conn.execute(
        """
        INSERT INTO faq_articles(title, created_at, updated_at, created_by)
        VALUES(?, ?, ?, ?)
        """,
        (title, created_at, created_at, created_by),
    )
    await conn.commit()
    article_id = int(cur.lastrowid)
    await conn.close()
    return article_id


async def list_articles() -> list[dict[str, Any]]:
    conn = await connect("faq.db")
    cur = await conn.execute(
        """
        SELECT id, title, created_at, updated_at
        FROM faq_articles
        ORDER BY updated_at DESC, id DESC
        """
    )
    rows = [dict(r) for r in await cur.fetchall()]
    await conn.close()
    return rows


async def get_article(article_id: int) -> Optional[dict[str, Any]]:
    conn = await connect("faq.db")
    cur = await conn.execute(
        "SELECT id, title, created_at, updated_at, created_by FROM faq_articles WHERE id = ?",
        (article_id,),
    )
    row = await cur.fetchone()
    await conn.close()
    return dict(row) if row else None


async def get_steps(article_id: int) -> list[dict[str, Any]]:
    conn = await connect("faq.db")
    cur = await conn.execute(
        """
        SELECT step_index, text, photo_path, created_at
        FROM faq_steps
        WHERE article_id = ?
        ORDER BY step_index ASC, id ASC
        """,
        (article_id,),
    )
    rows = [dict(r) for r in await cur.fetchall()]
    await conn.close()
    return rows


async def get_next_step_index(article_id: int) -> int:
    conn = await connect("faq.db")
    cur = await conn.execute(
        "SELECT MAX(step_index) as max_step FROM faq_steps WHERE article_id = ?",
        (article_id,),
    )
    row = await cur.fetchone()
    await conn.close()
    max_step = row["max_step"] if row else None
    return int(max_step) + 1 if max_step is not None else 1


async def add_step(
    article_id: int,
    step_index: int,
    text: str,
    photo_path: Optional[str],
    created_at: str,
) -> None:
    conn = await connect("faq.db")
    await conn.execute(
        """
        INSERT INTO faq_steps(article_id, step_index, text, photo_path, created_at)
        VALUES(?, ?, ?, ?, ?)
        """,
        (article_id, step_index, text, photo_path, created_at),
    )
    await conn.execute(
        "UPDATE faq_articles SET updated_at = ? WHERE id = ?",
        (created_at, article_id),
    )
    await conn.commit()
    await conn.close()
