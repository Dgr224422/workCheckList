from typing import Any, Optional

from app.db.base import connect


async def init() -> None:
    conn = await connect("checklists.db")
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS checklist_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS checklist_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            step_order INTEGER NOT NULL,
            text TEXT NOT NULL,
            FOREIGN KEY(template_id) REFERENCES checklist_templates(id) ON DELETE CASCADE
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS checklist_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            worker_id INTEGER NOT NULL,
            run_date TEXT NOT NULL,
            done_at TEXT,
            FOREIGN KEY(template_id) REFERENCES checklist_templates(id) ON DELETE CASCADE
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS checklist_run_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            step_id INTEGER NOT NULL,
            is_done INTEGER NOT NULL DEFAULT 0,
            photo_path TEXT,
            done_at TEXT,
            FOREIGN KEY(run_id) REFERENCES checklist_runs(id) ON DELETE CASCADE,
            FOREIGN KEY(step_id) REFERENCES checklist_steps(id) ON DELETE CASCADE
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            weekday INTEGER,
            exact_date TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
        """
    )
    await conn.commit()
    await conn.close()


async def create_template(title: str, created_by: int, created_at: str) -> int:
    conn = await connect("checklists.db")
    cur = await conn.execute(
        "INSERT INTO checklist_templates(title, created_by, created_at) VALUES(?, ?, ?)",
        (title, created_by, created_at),
    )
    await conn.commit()
    template_id = cur.lastrowid
    await conn.close()
    return int(template_id)


async def add_step(template_id: int, step_order: int, text: str) -> None:
    conn = await connect("checklists.db")
    await conn.execute(
        "INSERT INTO checklist_steps(template_id, step_order, text) VALUES(?, ?, ?)",
        (template_id, step_order, text),
    )
    await conn.commit()
    await conn.close()


async def list_templates() -> list[dict[str, Any]]:
    conn = await connect("checklists.db")
    cur = await conn.execute("SELECT * FROM checklist_templates ORDER BY id DESC")
    rows = [dict(r) for r in await cur.fetchall()]
    await conn.close()
    return rows


async def template_steps(template_id: int) -> list[dict[str, Any]]:
    conn = await connect("checklists.db")
    cur = await conn.execute(
        "SELECT * FROM checklist_steps WHERE template_id=? ORDER BY step_order",
        (template_id,),
    )
    rows = [dict(r) for r in await cur.fetchall()]
    await conn.close()
    return rows


async def create_run(template_id: int, worker_id: int, run_date: str) -> int:
    conn = await connect("checklists.db")
    cur = await conn.execute(
        "INSERT INTO checklist_runs(template_id, worker_id, run_date) VALUES(?, ?, ?)",
        (template_id, worker_id, run_date),
    )
    run_id = int(cur.lastrowid)
    steps_cur = await conn.execute(
        "SELECT id FROM checklist_steps WHERE template_id=? ORDER BY step_order",
        (template_id,),
    )
    steps = await steps_cur.fetchall()
    for step in steps:
        await conn.execute(
            "INSERT INTO checklist_run_steps(run_id, step_id) VALUES(?, ?)",
            (run_id, step["id"]),
        )
    await conn.commit()
    await conn.close()
    return run_id


async def run_steps(run_id: int) -> list[dict[str, Any]]:
    conn = await connect("checklists.db")
    cur = await conn.execute(
        """
        SELECT rs.id as run_step_id, rs.is_done, rs.photo_path, s.text, s.step_order
        FROM checklist_run_steps rs
        JOIN checklist_steps s ON s.id = rs.step_id
        WHERE rs.run_id=?
        ORDER BY s.step_order
        """,
        (run_id,),
    )
    rows = [dict(r) for r in await cur.fetchall()]
    await conn.close()
    return rows


async def get_run_id_for_step(run_step_id: int) -> Optional[int]:
    conn = await connect("checklists.db")
    cur = await conn.execute(
        "SELECT run_id FROM checklist_run_steps WHERE id=?",
        (run_step_id,),
    )
    row = await cur.fetchone()
    await conn.close()
    return int(row["run_id"]) if row else None


async def run_steps_recent_photos(limit: int = 10) -> list[dict[str, Any]]:
    conn = await connect("checklists.db")
    cur = await conn.execute(
        """
        SELECT rs.id as run_step_id, rs.photo_path, rs.done_at, cr.run_date,
               s.text, cr.id as run_id
        FROM checklist_run_steps rs
        JOIN checklist_runs cr ON cr.id = rs.run_id
        JOIN checklist_steps s ON s.id = rs.step_id
        WHERE rs.photo_path IS NOT NULL
        ORDER BY rs.done_at DESC, rs.id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = [dict(r) for r in await cur.fetchall()]
    await conn.close()
    return rows


async def mark_run_step(run_step_id: int, photo_path: Optional[str], done_at: str) -> None:
    conn = await connect("checklists.db")
    await conn.execute(
        "UPDATE checklist_run_steps SET is_done=1, photo_path=?, done_at=? WHERE id=?",
        (photo_path, done_at, run_step_id),
    )
    await conn.commit()
    await conn.close()


async def add_reminder(
    worker_id: int,
    title: str,
    weekday: Optional[int],
    exact_date: Optional[str],
    created_at: str,
) -> None:
    conn = await connect("checklists.db")
    await conn.execute(
        "INSERT INTO reminders(worker_id, title, weekday, exact_date, created_at) VALUES(?, ?, ?, ?, ?)",
        (worker_id, title, weekday, exact_date, created_at),
    )
    await conn.commit()
    await conn.close()


async def active_reminders() -> list[dict[str, Any]]:
    conn = await connect("checklists.db")
    cur = await conn.execute("SELECT * FROM reminders WHERE is_active=1")
    rows = [dict(r) for r in await cur.fetchall()]
    await conn.close()
    return rows
