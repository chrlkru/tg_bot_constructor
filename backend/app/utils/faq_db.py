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
CREATE TABLE IF NOT EXISTS faq (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    question   TEXT,
    answer     TEXT,
    media      TEXT
)""")
conn.commit()

def safe_execute(query: str, params: tuple = ()):
    """Безопасно выполнить SQL-запрос и вернуть результат или None."""
    try:
        cur.execute(query, params)
        if query.strip().upper().startswith("SELECT"):
            return cur.fetchall()
        else:
            conn.commit()
            if query.strip().upper().startswith("INSERT"):
                return cur.lastrowid
            else:
                return cur.rowcount
    except Exception as e:
        print(f"Database error: {e}")
        return None

def transaction(func):
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

def get_faq_entries(project_id: int):
    """Вернуть список всех FAQ-записей для проекта."""
    res = safe_execute("SELECT * FROM faq WHERE project_id=?", (project_id,))
    return res if res is not None else []

def add_faq_entry(project_id: int, question: str, answer: str, media: str = ""):
    """Добавить новый FAQ; вернуть его ID."""
    return safe_execute(
        "INSERT INTO faq(project_id, question, answer, media) VALUES (?, ?, ?, ?)",
        (project_id, question, answer, media)
    )

def delete_faq_entry(project_id: int, entry_id: int):
    """Удалить FAQ-запись по ее ID."""
    return safe_execute("DELETE FROM faq WHERE project_id=? AND id=?", (project_id, entry_id))
