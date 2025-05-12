import sqlite3
from pathlib import Path
from contextlib import contextmanager

# Подключение к базе данных (Feedback bot)
DB_PATH = Path(__file__).parent / "feedback_bot.db"
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("PRAGMA foreign_keys = ON")

# Создание таблиц для сообщений и блокировок
cur.execute("""
CREATE TABLE IF NOT EXISTS feedback (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    user_id    INTEGER,
    direction  TEXT,  -- 'in' или 'out'
    text       TEXT
)""")
cur.execute("""
CREATE TABLE IF NOT EXISTS blocked_users (
    project_id INTEGER,
    user_id    INTEGER,
    PRIMARY KEY(project_id, user_id)
)""")
conn.commit()

def safe_execute(query: str, params: tuple = ()):
    """Безопасное выполнение SQL-запроса."""
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
    """Декоратор для атомарного выполнения операций с БД."""
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

def log_feedback(project_id: int, user_id: int, direction: str, text: str):
    """Сохранить сообщение фидбека (direction = 'in' для входящего, 'out' для ответа)."""
    return safe_execute(
        "INSERT INTO feedback(project_id, user_id, direction, text) VALUES (?, ?, ?, ?)",
        (project_id, user_id, direction, text)
    )

def block_user(project_id: int, user_id: int):
    """Заблокировать пользователя (занести в список blocked_users)."""
    return safe_execute(
        "INSERT OR IGNORE INTO blocked_users(project_id, user_id) VALUES (?, ?)",
        (project_id, user_id)
    )

def is_blocked(project_id: int, user_id: int) -> bool:
    """Проверить, находится ли пользователь в черном списке (заблокирован)."""
    res = safe_execute("SELECT 1 FROM blocked_users WHERE project_id=? AND user_id=?", (project_id, user_id))
    return res is not None and len(res) > 0
