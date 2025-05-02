# app/utils/feedback.py
import time
from pathlib import Path
from app.utils.db_safe import transaction, safe_execute

DB_PATH = Path(__file__).resolve().parent.parent / "app" / "database.db"

# ── CRUD блок‑листа ──────────────────────────────
def block_user(project_id: int, user_id: int):
    with transaction(DB_PATH) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO feedback_blocked(project_id,user_id) VALUES(?,?)",
            (project_id, user_id)
        )

def is_blocked(project_id: int, user_id: int) -> bool:
    rows = safe_execute(
        "SELECT 1 FROM feedback_blocked WHERE project_id=? AND user_id=?",
        (project_id, user_id),
        DB_PATH
    )
    return bool(rows)

# ── Логирование сообщений ───────────────────────
def log_feedback(project_id:int, user_id:int, direction:str, text:str):
    ts = int(time.time())
    with transaction(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO feedback_messages(project_id,user_id,direction,text,ts) "
            "VALUES(?,?,?,?,?)",
            (project_id, user_id, direction, text, ts)
        )
