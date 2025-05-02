# app/utils/db_safe.py

import sqlite3
from pathlib import Path
from contextlib import contextmanager

# Путь к файлу базы данных (при необходимости скорректируйте)
DB_PATH = Path(__file__).resolve().parent.parent / "database.db"

@contextmanager
def transaction(db_path: Path | str = DB_PATH):
    """
    Контекст-менеджер для транзакции SQLite:
    - BEGIN IMMEDIATE: блокировка БД на запись
    - commit при успешном выходе
    - rollback при ошибке
    """
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("BEGIN IMMEDIATE;")
        yield conn
        conn.commit()
    except:
        conn.rollback()
        raise
    finally:
        conn.close()

def safe_execute(
    sql: str,
    params: tuple = (),
    db_path: Path | str = DB_PATH
) -> list[tuple]:
    """
    Выполняет произвольный SQL в рамках транзакции и возвращает результаты.
    Использует transaction() для защиты от гонок и неконсистентности.
    """
    with transaction(db_path) as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall()
