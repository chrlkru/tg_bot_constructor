import sqlite3
from pathlib import Path
from contextlib import contextmanager

# Подключение к базе данных (FAQ bot)
DB_PATH = Path(__file__).parent / "faq_bot.db"
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("PRAGMA foreign_keys = ON")

# Создание таблицы FAQ
cur.execute("""
CREATE TABLE IF NOT EXISTS faq_entries (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    question   TEXT,
    answer     TEXT,
    media_path TEXT
)""")
conn.commit()

def safe_execute(query: str, params: tuple = ()):  # pragma: no cover
    """Безопасно выполнить SQL-запрос и вернуть результат или None."""
    try:
        cur.execute(query, params)
        sql = query.strip().upper()
        if sql.startswith("SELECT"):
            return cur.fetchall()
        conn.commit()
        if sql.startswith("INSERT"):
            return cur.lastrowid
        return cur.rowcount
    except Exception as e:
        print(f"Database error: {e}")
        return None


def transaction(func):  # pragma: no cover
    """Декоратор для выполнения серии SQL-запросов транзакционно."""
    def wrapper(*args, **kwargs):
        try:
            cur.execute("BEGIN")
            result = func(*args, **kwargs)
            conn.commit()
            return result
        except Exception as e:
            conn.rollback()
            print(f"Transaction error in {func.__name__}: {e}")
            return None
    return wrapper


def get_faq_entries(project_id: int) -> list[dict]:
    with _conn() as db:
        cur = db.execute(
            "SELECT id, question, answer, media_path FROM faq_entries WHERE project_id = ? ORDER BY id",
            (project_id,)
        )
        return [
            {
                "id": row["id"],
                "question": row["question"],
                "answer": row["answer"],
                "media": row["media_path"] or ""
            }
            for row in cur.fetchall()
        ]



def add_faq_entry(project_id: int, question: str, answer: str, media_path: str = ""):
    """Добавить новый FAQ; вернуть его ID."""
    return safe_execute(
        "INSERT INTO faq_entries(project_id, question, answer, media_path) VALUES (?, ?, ?, ?)",
        (project_id, question, answer, media_path)
    )


def delete_faq_entry(project_id: int, entry_id: int):
    """Удалить FAQ-запись по ее ID."""
    return safe_execute(
        "DELETE FROM faq_entries WHERE project_id = ? AND id = ?",
        (project_id, entry_id)
    )
