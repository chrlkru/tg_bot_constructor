import sqlite3
from pathlib import Path

# Путь к файлу БД helper-бота
DB_PATH = Path(__file__).parent / "helper_bot.db"

# Открываем соединение; check_same_thread=False — чтобы избежать проблем в многопоточном окружении
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.row_factory = sqlite3.Row

def safe_execute(query: str, params: tuple = ()):
    """Выполнить SQL-запрос и вернуть результат."""
    with conn:
        cur = conn.execute(query, params)
        cmd = query.strip().split()[0].upper()
        if cmd == "SELECT":
            return cur.fetchall()
        elif cmd == "INSERT":
            return cur.lastrowid
        else:
            return cur.rowcount

# Создание таблицы helper_entries с добавленным столбцом admin_only
safe_execute("""
CREATE TABLE IF NOT EXISTS helper_entries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   INTEGER,
    alias        TEXT,
    content      TEXT,
    media_path   TEXT,
    admin_only   BOOLEAN    DEFAULT 0,
    UNIQUE(project_id, alias)
)
""")

def add_helper_entry(project_id: int,
                     alias: str,
                     content: str,
                     media_path: str = "",
                     admin_only: bool = False) -> int:
    """Добавить новую пасту. Возвращает ID записи."""
    return safe_execute(
        "INSERT INTO helper_entries(project_id, alias, content, media_path, admin_only) VALUES (?, ?, ?, ?, ?)",
        (project_id, alias, content, media_path, int(admin_only))
    )

def get_helper_by_alias(project_id: int,
                        alias: str,
                        is_admin: bool = False):
    """
    Получить пасту по alias.
    Если is_admin=False, скрываем записи с admin_only=1.
    Возвращает (content, media_path) или None.
    """
    if is_admin:
        rows = safe_execute(
            "SELECT content, media_path FROM helper_entries WHERE project_id=? AND alias=?",
            (project_id, alias)
        )
    else:
        rows = safe_execute(
            "SELECT content, media_path FROM helper_entries WHERE project_id=? AND alias=? AND admin_only=0",
            (project_id, alias)
        )
    if not rows:
        return None
    row = rows[0]
    return row["content"], row["media_path"]

def get_all_helper_entries(project_id: int,
                           is_admin: bool = False):
    """
    Вернуть список всех паст для проекта.
    Если is_admin=False, фильтруем admin_only=0.
    """
    if is_admin:
        return safe_execute(
            "SELECT id, alias, content, media_path, admin_only FROM helper_entries WHERE project_id=? ORDER BY id",
            (project_id,)
        ) or []
    else:
        return safe_execute(
            "SELECT id, alias, content, media_path FROM helper_entries WHERE project_id=? AND admin_only=0 ORDER BY id",
            (project_id,)
        ) or []

def update_helper_entry(project_id: int,
                        entry_id: int,
                        alias: str = None,
                        content: str = None,
                        media_path: str = None,
                        admin_only: bool = None) -> int:
    """
    Обновить поля записи.
    Параметры, равные None, не меняются.
    Возвращает число изменённых строк.
    """
    parts, params = [], []
    if alias is not None:
        parts.append("alias = ?");       params.append(alias)
    if content is not None:
        parts.append("content = ?");     params.append(content)
    if media_path is not None:
        parts.append("media_path = ?");  params.append(media_path)
    if admin_only is not None:
        parts.append("admin_only = ?");  params.append(int(admin_only))
    if not parts:
        return 0
    params.extend([project_id, entry_id])
    sql = f"UPDATE helper_entries SET {', '.join(parts)} WHERE project_id=? AND id=?"
    return safe_execute(sql, tuple(params))

def delete_helper_entry(project_id: int, entry_id: int) -> int:
    """Удалить пасту по ID; возвращает число удалённых строк."""
    return safe_execute(
        "DELETE FROM helper_entries WHERE project_id=? AND id=?",
        (project_id, entry_id)
    )
