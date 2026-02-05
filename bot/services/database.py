from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import aiosqlite


@dataclass(slots=True)
class Checklist:
    id: int
    title: str


@dataclass(slots=True)
class ChecklistItem:
    id: int
    checklist_id: int
    text: str
    sort_order: int


@dataclass(slots=True)
class Submission:
    id: int
    user_id: int
    checklist_id: int
    created_at: str


@dataclass(slots=True)
class SubmissionItem:
    id: int
    submission_id: int
    item_id: int
    done: bool
    comment: str


class Database:
    def __init__(self, path: str):
        self.path = path

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    full_name TEXT NOT NULL,
                    username TEXT,
                    is_admin INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS checklists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS checklist_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    checklist_id INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    sort_order INTEGER NOT NULL,
                    FOREIGN KEY (checklist_id) REFERENCES checklists(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    checklist_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (checklist_id) REFERENCES checklists(id)
                );

                CREATE TABLE IF NOT EXISTS submission_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id INTEGER NOT NULL,
                    item_id INTEGER NOT NULL,
                    done INTEGER NOT NULL,
                    comment TEXT NOT NULL,
                    FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE,
                    FOREIGN KEY (item_id) REFERENCES checklist_items(id)
                );
                """
            )
            await db.commit()

    async def register_user(self, user_id: int, full_name: str, username: str | None, is_admin: bool) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO users(user_id, full_name, username, is_admin, created_at)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(user_id)
                DO UPDATE SET full_name=excluded.full_name, username=excluded.username, is_admin=excluded.is_admin
                """,
                (user_id, full_name, username, int(is_admin), now),
            )
            await db.commit()

    async def create_checklist(self, title: str) -> int:
        now = datetime.utcnow().isoformat(timespec="seconds")
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "INSERT INTO checklists(title, created_at) VALUES(?, ?)",
                (title, now),
            )
            await db.commit()
            return cursor.lastrowid

    async def add_checklist_item(self, checklist_id: int, text: str) -> int:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "SELECT COALESCE(MAX(sort_order), 0) + 1 FROM checklist_items WHERE checklist_id = ?",
                (checklist_id,),
            )
            row = await cursor.fetchone()
            sort_order = row[0]
            insert = await db.execute(
                "INSERT INTO checklist_items(checklist_id, text, sort_order) VALUES(?, ?, ?)",
                (checklist_id, text, sort_order),
            )
            await db.commit()
            return insert.lastrowid

    async def list_checklists(self) -> list[Checklist]:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("SELECT id, title FROM checklists ORDER BY id")
            rows = await cursor.fetchall()
        return [Checklist(id=row[0], title=row[1]) for row in rows]

    async def get_checklist_items(self, checklist_id: int) -> list[ChecklistItem]:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                """
                SELECT id, checklist_id, text, sort_order
                FROM checklist_items
                WHERE checklist_id = ?
                ORDER BY sort_order
                """,
                (checklist_id,),
            )
            rows = await cursor.fetchall()
        return [ChecklistItem(id=r[0], checklist_id=r[1], text=r[2], sort_order=r[3]) for r in rows]

    async def create_submission(self, user_id: int, checklist_id: int) -> int:
        now = datetime.utcnow().isoformat(timespec="seconds")
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "INSERT INTO submissions(user_id, checklist_id, created_at) VALUES(?, ?, ?)",
                (user_id, checklist_id, now),
            )
            await db.commit()
            return cursor.lastrowid

    async def add_submission_item(self, submission_id: int, item_id: int, done: bool, comment: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO submission_items(submission_id, item_id, done, comment) VALUES(?, ?, ?, ?)",
                (submission_id, item_id, int(done), comment),
            )
            await db.commit()

    async def get_user_submissions(self, user_id: int) -> list[Submission]:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "SELECT id, user_id, checklist_id, created_at FROM submissions WHERE user_id = ? ORDER BY id DESC",
                (user_id,),
            )
            rows = await cursor.fetchall()
        return [Submission(id=r[0], user_id=r[1], checklist_id=r[2], created_at=r[3]) for r in rows]

    async def get_submission_report(self, submission_id: int) -> tuple[Submission, str, str, list[SubmissionItem]] | None:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                """
                SELECT s.id, s.user_id, s.checklist_id, s.created_at,
                       c.title, u.full_name
                FROM submissions s
                JOIN checklists c ON c.id = s.checklist_id
                JOIN users u ON u.user_id = s.user_id
                WHERE s.id = ?
                """,
                (submission_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            submission = Submission(id=row[0], user_id=row[1], checklist_id=row[2], created_at=row[3])
            checklist_title = row[4]
            full_name = row[5]
            items_cur = await db.execute(
                """
                SELECT si.id, si.submission_id, si.item_id, si.done, si.comment
                FROM submission_items si
                WHERE si.submission_id = ?
                ORDER BY si.id
                """,
                (submission_id,),
            )
            item_rows = await items_cur.fetchall()
        items = [SubmissionItem(id=i[0], submission_id=i[1], item_id=i[2], done=bool(i[3]), comment=i[4]) for i in item_rows]
        return submission, checklist_title, full_name, items

    async def list_all_submissions(self, limit: int = 20) -> list[tuple[int, str, str, str]]:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                """
                SELECT s.id, u.full_name, c.title, s.created_at
                FROM submissions s
                JOIN users u ON u.user_id = s.user_id
                JOIN checklists c ON c.id = s.checklist_id
                ORDER BY s.id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cursor.fetchall()
        return [(r[0], r[1], r[2], r[3]) for r in rows]
