import sqlite3
from pathlib import Path
from contextlib import contextmanager

# Подключение к базе данных (Moderator bot)
DB_PATH = Path(__file__).parent / "moderator_bot.db"
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("PRAGMA foreign_keys = ON")

# Создание таблиц модерации
cur.execute("""
CREATE TABLE IF NOT EXISTS settings (
    project_id INTEGER,
    key       TEXT,
    value     TEXT,
    PRIMARY KEY(project_id, key)
)""")
cur.execute("""
CREATE TABLE IF NOT EXISTS strikes (
    project_id INTEGER,
    chat_id    INTEGER,
    user_id    INTEGER,
    count      INTEGER,
    PRIMARY KEY(project_id, chat_id, user_id)
)""")
cur.execute("""
CREATE TABLE IF NOT EXISTS violations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    chat_id    INTEGER,
    user_id    INTEGER,
    message_id INTEGER,
    violations TEXT,
    text       TEXT
)""")
cur.execute("""
CREATE TABLE IF NOT EXISTS whitelist (
    project_id INTEGER,
    user_id    INTEGER,
    PRIMARY KEY(project_id, user_id)
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
    """Декоратор для транзакционного выполнения операций БД."""
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

def check_message(project_id: int, chat_id: int, user_id: int, text: str, content_type: str):
    """
    Проверить сообщение на нарушения. Возвращает список меток нарушений или пустой список.
    """
    violations = []
    # Правило: если сообщение содержит медиа, а медиа запрещены
    allow_media = (get_setting(project_id, 'allow_media') or "1") in ("1", "True", "true")
    if content_type in ("photo", "video", "document") and not allow_media:
        violations.append("media")
    # Простейшее правило для спама: слишком длинное сообщение
    if text and len(text) > 200:
        violations.append("spam")
    return violations

def add_strike(project_id: int, chat_id: int, user_id: int) -> int:
    """Добавить предупреждение (strike) пользователю и вернуть новое количество."""
    res = safe_execute(
        "SELECT count FROM strikes WHERE project_id=? AND chat_id=? AND user_id=?",
        (project_id, chat_id, user_id)
    )
    current = res[0]["count"] if res and len(res) > 0 else 0
    new_count = current + 1
    if current == 0:
        safe_execute(
            "INSERT INTO strikes(project_id, chat_id, user_id, count) VALUES (?, ?, ?, ?)",
            (project_id, chat_id, user_id, new_count)
        )
    else:
        safe_execute(
            "UPDATE strikes SET count=? WHERE project_id=? AND chat_id=? AND user_id=?",
            (new_count, project_id, chat_id, user_id)
        )
    return new_count

def log_violation(project_id: int, chat_id: int, user_id: int, message_id: int, violations: str, text: str):
    """Залогировать нарушение в таблицу."""
    return safe_execute(
        "INSERT INTO violations(project_id, chat_id, user_id, message_id, violations, text) VALUES (?, ?, ?, ?, ?, ?)",
        (project_id, chat_id, user_id, message_id, violations, text)
    )

def format_report(reporter, chat_id: int, message_id: int, reason: str) -> str:
    """Сформатировать текст жалобы для отправки админу."""
    return (f"🚨 <b>Report</b>\n"
            f"Reporter: {reporter}\n"
            f"Chat ID: {chat_id}\n"
            f"Message ID: {message_id}\n"
            f"Reason: {reason if reason else 'No reason provided'}")

def toggle_setting(project_id: int, key: str, value):
    """Изменить (переключить) настройку модерации (например, включить/выключить медиа)."""
    val_str = "1" if str(value).lower() in ("1", "true", "yes", "on") else "0"
    existing = safe_execute("SELECT value FROM settings WHERE project_id=? AND key=?", (project_id, key))
    if existing is None:
        return None
    if len(existing) > 0:
        safe_execute("UPDATE settings SET value=? WHERE project_id=? AND key=?", (val_str, project_id, key))
    else:
        safe_execute("INSERT INTO settings(project_id, key, value) VALUES (?, ?, ?)", (project_id, key, val_str))
    return val_str

def whitelist_add(project_id: int, user_id: int):
    """Добавить пользователя в whitelist (исключить из авто-модерации)."""
    return safe_execute("INSERT OR IGNORE INTO whitelist(project_id, user_id) VALUES (?, ?)", (project_id, user_id))

def whitelist_del(project_id: int, user_id: int):
    """Удалить пользователя из whitelist."""
    return safe_execute("DELETE FROM whitelist WHERE project_id=? AND user_id=?", (project_id, user_id))

def list_whitelist(project_id: int):
    """Получить список всех пользователей в whitelist."""
    res = safe_execute("SELECT user_id FROM whitelist WHERE project_id=?", (project_id,))
    return [row["user_id"] for row in res] if res is not None else []

def get_settings(project_id: int):
    """Получить все настройки проекта в виде словаря."""
    res = safe_execute("SELECT key, value FROM settings WHERE project_id=?", (project_id,))
    return {row["key"]: row["value"] for row in res} if res is not None else {}

def get_setting(project_id: int, key: str):
    """Получить значение одной настройки (или None, если не задано)."""
    res = safe_execute("SELECT value FROM settings WHERE project_id=? AND key=?", (project_id, key))
    if res and len(res) > 0:
        return res[0]["value"]
    return None
