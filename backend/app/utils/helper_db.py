import sqlite3
from pathlib import Path
from contextlib import contextmanager

# Подключение к базе данных (Helper bot)
DB_PATH = Path(__file__).parent / "helper_bot.db"
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("PRAGMA foreign_keys = ON")

# Создание таблицы для паст (helper entries)
cur.execute("""
CREATE TABLE IF NOT EXISTS helper (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    alias      TEXT,
    content    TEXT,
    media      TEXT,
    UNIQUE(project_id, alias)
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
    """Декоратор для атомарного выполнения операций в базе данных."""
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

def add_helper_entry(project_id: int, alias: str, content: str, media: str = ""):
    """Добавить новую пасту. Возвращает ID записи."""
    return safe_execute(
        "INSERT INTO helper(project_id, alias, content, media) VALUES (?, ?, ?, ?)",
        (project_id, alias, content, media)
    )

def get_helper_by_alias(project_id: int, alias: str):
    """Получить пасту по ее алиасу. Возвращает (content, media) или None."""
    res = safe_execute("SELECT content, media FROM helper WHERE project_id=? AND alias=?", (project_id, alias))
    if res is None or len(res) == 0:
        return None
    row = res[0]
    return (row["content"], row["media"])

def get_all_helper_entries(project_id: int):
    """Вернуть список всех паст для проекта."""
    res = safe_execute("SELECT * FROM helper WHERE project_id=?", (project_id,))
    return res if res is not None else []

def update_helper_entry(project_id: int, entry_id: int, alias: str = None, content: str = None, media_path: str = None):
    """Обновить поля записи пасты (alias, content и/или media)."""
    updates = []
    params = []
    if alias is not None:
        updates.append("alias = ?")
        params.append(alias)
    if content is not None:
        updates.append("content = ?")
        params.append(content)
    if media_path is not None:
        updates.append("media = ?")
        params.append(media_path)
    if not updates:
        return None
    params.extend([project_id, entry_id])
    query = f"UPDATE helper SET {', '.join(updates)} WHERE project_id=? AND id=?"
    return safe_execute(query, tuple(params))

def delete_helper_entry(project_id: int, entry_id: int):
    """Удалить пасту по ее ID."""
    return safe_execute("DELETE FROM helper WHERE project_id=? AND id=?", (project_id, entry_id))
