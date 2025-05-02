# app/utils/helper.py

import sqlite3
from pathlib import Path
from app.utils.db_safe import transaction, safe_execute

DB_PATH = Path(__file__).resolve().parent.parent / "app" / "database.db"

def add_helper_entry(project_id: int, alias: str, content: str, media_path: str="") -> int:
    with transaction(DB_PATH) as conn:
        cur = conn.execute(
            "INSERT INTO helper_entries(project_id,alias,content,media_path) VALUES(?,?,?,?)",
            (project_id, alias, content, media_path or "")
        )
        return cur.lastrowid

def get_helper_by_alias(project_id: int, alias: str):
    rows = safe_execute(
        "SELECT content, media_path FROM helper_entries WHERE project_id=? AND alias=?",
        (project_id, alias),
        DB_PATH
    )
    return rows[0] if rows else None

def get_all_helper_entries(project_id: int):
    rows = safe_execute(
        "SELECT id, alias, content, media_path FROM helper_entries WHERE project_id=? ORDER BY id",
        (project_id,),
        DB_PATH
    )
    return [{"id": r[0], "alias": r[1], "content": r[2], "media": r[3] or ""} for r in rows]

def update_helper_entry(project_id: int, entry_id: int,
                        alias: str = None, content: str = None, media_path: str = None) -> None:
    fields = []
    params = []
    if alias is not None:
        fields.append("alias=?")
        params.append(alias)
    if content is not None:
        fields.append("content=?")
        params.append(content)
    if media_path is not None:
        fields.append("media_path=?")
        params.append(media_path)
    if not fields:
        return
    params.extend([project_id, entry_id])
    with transaction(DB_PATH) as conn:
        conn.execute(
            f"UPDATE helper_entries SET {','.join(fields)} WHERE project_id=? AND id=?",
            tuple(params)
        )

def delete_helper_entry(project_id: int, entry_id: int) -> None:
    with transaction(DB_PATH) as conn:
        conn.execute(
            "DELETE FROM helper_entries WHERE project_id=? AND id=?",
            (project_id, entry_id)
        )
