# app/utils/slots.py

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.database import DB_PATH, create_booking

@contextmanager
def _transaction(db_path: Path | str = DB_PATH) -> Iterator[sqlite3.Connection]:
    """
    Открывает транзакцию BEGIN IMMEDIATE, чтобы заблокировать БД на запись.
    При выходе коммитит, либо при исключении — откатывает.
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

def is_slot_booked(conn: sqlite3.Connection, project_id: int, start_dt: str) -> bool:
    """
    Проверяет, есть ли в таблице bookings брони на проект и время start_dt.
    """
    cur = conn.execute(
        "SELECT 1 FROM bookings WHERE project_id=? AND start_dt=? AND status='confirmed'",
        (project_id, start_dt)
    )
    return cur.fetchone() is not None

def is_slot_blocked(conn: sqlite3.Connection, project_id: int, start_dt: str) -> bool:
    """
    Проверяет, попадает ли start_dt в активный work_exception.
    """
    cur = conn.execute(
        """
        SELECT 1 FROM work_exceptions
         WHERE project_id=?
           AND state='active'
           AND start_dt <= ?
           AND end_dt > ?
        """,
        (project_id, start_dt, start_dt)
    )
    return cur.fetchone() is not None

def create_booking_safe(
    project_id: int,
    user_id: int,
    service_id: int,
    start_dt: str,
    duration_cells: int,
    client_name: str,
    client_phone: str,
    db_path: Path | str = DB_PATH
) -> int:
    """
    Пытается забронировать слот atomically:
    1) BEGIN IMMEDIATE транзакция
    2) Проверки is_slot_booked / is_slot_blocked
    3) Если свободно, вызывает create_booking, иначе — ValueError
    Возвращает id новой записи.
    """
    with _transaction(db_path) as conn:
        if is_slot_blocked(conn, project_id, start_dt):
            raise ValueError("⛔ Слот заблокирован администратором")
        if is_slot_booked(conn, project_id, start_dt):
            raise ValueError("❌ Этот слот уже занят")
        # внутри той же транзакции:
        bid = create_booking(
            project_id, user_id, service_id,
            start_dt, duration_cells, client_name, client_phone
        )
        return bid
