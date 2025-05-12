import sqlite3
from pathlib import Path
from contextlib import contextmanager

# Подключение к базе данных (Booking CRM bot)
DB_PATH = Path(__file__).parent / "booking_bot.db"
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("PRAGMA foreign_keys = ON")

def init_db():
    """Инициализировать таблицы для бота бронирования."""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            name       TEXT,
            price      TEXT,
            duration   INTEGER,
            category   TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS work_intervals (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            date       TEXT,
            time       TEXT,
            UNIQUE(project_id, date, time)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS work_exceptions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            start      TEXT,
            end        TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            user_id    INTEGER,
            service_id INTEGER,
            slot_id    INTEGER,
            date       TEXT,
            time       TEXT,
            details    TEXT,
            UNIQUE(project_id, slot_id),
            FOREIGN KEY(slot_id) REFERENCES work_intervals(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            user_id    INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            project_id INTEGER,
            key        TEXT,
            value      TEXT,
            PRIMARY KEY(project_id, key)
        )
    """)
    conn.commit()

def safe_execute(query: str, params: tuple = ()):
    """Выполнить SQL-запрос с обработкой ошибок."""
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
    """Декоратор для выполнения операций в транзакции."""
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

def add_service(project_id: int, name: str, price: str, duration: int, category: str):
    """Добавить новую услугу."""
    return safe_execute(
        "INSERT INTO services(project_id, name, price, duration, category) VALUES (?, ?, ?, ?, ?)",
        (project_id, name, price, duration, category)
    )

def get_services(project_id: int, category: str = None):
    """Получить список услуг (опционально фильтрация по категории)."""
    if category:
        res = safe_execute("SELECT * FROM services WHERE project_id=? AND category=?", (project_id, category))
    else:
        res = safe_execute("SELECT * FROM services WHERE project_id=?", (project_id,))
    return res if res is not None else []

def delete_service(project_id: int, service_id: int):
    """Удалить услугу по ее ID."""
    return safe_execute("DELETE FROM services WHERE project_id=? AND id=?", (project_id, service_id))

def add_work_interval(project_id: int, date: str, time: str):
    """Добавить новое свободное окно (слот времени)."""
    return safe_execute(
        "INSERT OR IGNORE INTO work_intervals(project_id, date, time) VALUES (?, ?, ?)",
        (project_id, date, time)
    )

def delete_work_interval(project_id: int, date: str, time: str):
    """Удалить окно (слот) доступного времени."""
    slot = safe_execute("SELECT id FROM work_intervals WHERE project_id=? AND date=? AND time=?", (project_id, date, time))
    if slot and len(slot) > 0:
        slot_id = slot[0]["id"]
        cancel_bookings_in_interval(project_id, date + " " + time, date + " " + time)
        safe_execute("DELETE FROM work_intervals WHERE project_id=? AND id=?", (project_id, slot_id))
        return True
    return False

def add_work_exception(project_id: int, start: str, end: str):
    """Добавить исключение (нерабочий интервал) на указанный период."""
    return safe_execute(
        "INSERT INTO work_exceptions(project_id, start, end) VALUES (?, ?, ?)",
        (project_id, start, end)
    )

def cancel_bookings_in_interval(project_id: int, start: str, end: str):
    """Отменить (удалить) все брони в заданном интервале времени [start, end]."""
    return safe_execute(
        "DELETE FROM bookings WHERE project_id=? AND (date || ' ' || time) >= ? AND (date || ' ' || time) <= ?",
        (project_id, start, end)
    )

def get_planned_exceptions(project_id: int):
    """Получить все запланированные исключения (закрытые интервалы)."""
    res = safe_execute("SELECT * FROM work_exceptions WHERE project_id=?", (project_id,))
    return res if res is not None else []

def get_confirmed_future_bookings(project_id: int):
    """Получить все будущие бронирования (на момент текущего времени)."""
    import datetime
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    res = safe_execute(
        "SELECT * FROM bookings WHERE project_id=? AND (date || ' ' || time) >= ?",
        (project_id, now)
    )
    return res if res is not None else []

def create_booking_safe(project_id: int, user_id: int, service_id: int, slot_id: int, details: str = ""):
    """Безопасно создать новую бронь (если слот еще свободен). Возвращает ID брони или None."""
    try:
        cur.execute("BEGIN")
        # Получаем дату и время слота
        cur.execute("SELECT date, time FROM work_intervals WHERE project_id=? AND id=?", (project_id, slot_id))
        row = cur.fetchone()
        if row is None:
            conn.rollback()
            return None
        slot_date, slot_time = row["date"], row["time"]
        # Пытаемся вставить новую бронь (уникальность slot_id гарантирует один бронированный пользователь на слот)
        try:
            cur.execute(
                "INSERT INTO bookings(project_id, user_id, service_id, slot_id, date, time, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (project_id, user_id, service_id, slot_id, slot_date, slot_time, details)
            )
        except Exception as e:
            # Нарушение уникальности (слот уже забронирован)
            conn.rollback()
            print(f"Booking insert error: {e}")
            return None
        # Добавляем запись о клиенте, если его еще нет
        cur.execute("SELECT id FROM clients WHERE project_id=? AND user_id=?", (project_id, user_id))
        if cur.fetchone() is None:
            cur.execute("INSERT INTO clients(project_id, user_id) VALUES (?, ?)", (project_id, user_id))
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        conn.rollback()
        print(f"Transaction error in create_booking_safe: {e}")
        return None

def get_booking(booking_id: int):
    """Получить детали бронирования по его ID (включая название услуги)."""
    res = safe_execute(
        "SELECT b.id, b.user_id, b.date, b.time, b.details, s.name as service_name "
        "FROM bookings b JOIN services s ON b.service_id=s.id WHERE b.id=?",
        (booking_id,)
    )
    if res and len(res) > 0:
        return res[0]
    return None

def get_bookings_by_date(project_id: int, date: str):
    """Получить все брони на указанную дату."""
    res = safe_execute("SELECT * FROM bookings WHERE project_id=? AND date=?", (project_id, date))
    return res if res is not None else []

def get_all_clients(project_id: int):
    """Получить список всех уникальных пользователей с бронированиями."""
    res = safe_execute("SELECT DISTINCT user_id FROM bookings WHERE project_id=?", (project_id,))
    return [row["user_id"] for row in res] if res is not None else []

def get_all_bookings(project_id: int):
    """Получить все брони для проекта."""
    res = safe_execute("SELECT * FROM bookings WHERE project_id=?", (project_id,))
    return res if res is not None else []

def get_setting(project_id: int, key: str):
    """Получить значение настройки (из таблицы settings)."""
    res = safe_execute("SELECT value FROM settings WHERE project_id=? AND key=?", (project_id, key))
    if res and len(res) > 0:
        return res[0]["value"]
    return None

def set_setting(project_id: int, key: str, value: str):
    """Установить или обновить настройку (в таблице settings)."""
    existing = safe_execute("SELECT value FROM settings WHERE project_id=? AND key=?", (project_id, key))
    if existing is None:
        return None
    if len(existing) > 0:
        safe_execute("UPDATE settings SET value=? WHERE project_id=? AND key=?", (value, project_id, key))
    else:
        safe_execute("INSERT INTO settings(project_id, key, value) VALUES (?, ?, ?)", (project_id, key, value))
    return value
