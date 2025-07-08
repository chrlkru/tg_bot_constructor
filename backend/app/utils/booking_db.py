import sqlite3
from pathlib import Path
from contextlib import contextmanager
from collections import namedtuple
from datetime import date, datetime
from openpyxl import Workbook
import calendar

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
    user_id    INTEGER,
    name       TEXT,
    phone      TEXT,
    UNIQUE(project_id, user_id)
);
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


# --- в начале файла, после init_db() ---

def get_slots_by_date(project_id: int, date: str):
    """
    Возвращает все слоты (work_intervals) на указанную дату.
    Каждый элемент — sqlite3.Row с полями: id, project_id, date, time.
    """
    rows = safe_execute(
        "SELECT * FROM work_intervals WHERE project_id=? AND date=? ORDER BY time",
        (project_id, date)
    )
    return rows or []


def export_clients_to_workbook(project_id: int) -> Workbook:
    """
    Формирует Workbook со списком клиентов.
    Лист: Clients  (id, user_id, name, phone).
    """
    rows = safe_execute(
        "SELECT id, user_id, name, phone "
        "FROM clients WHERE project_id=? ORDER BY id",
        (project_id,)
    ) or []

    wb = Workbook()
    ws = wb.active
    ws.title = "Clients"
    ws.append(["ID", "Telegram ID", "Name", "Phone"])

    for r in rows:
        ws.append([r["id"], r["user_id"], r["name"], r["phone"]])

    return wb


def export_bookings_to_workbook(project_id: int) -> Workbook:
    """
    Workbook с бронями (совмещает услуги и клиента).
    Лист: Bookings
    """
    sql = """
    SELECT
        b.id          AS booking_id,
        b.date,
        b.time,
        s.name        AS service,
        cl.name       AS client_name,
        cl.phone      AS phone,
        b.details
    FROM bookings b
    JOIN services s ON s.id = b.service_id
    JOIN clients  cl ON cl.user_id = b.user_id AND cl.project_id = b.project_id
    WHERE b.project_id=?
    ORDER BY b.date, b.time
    """
    rows = safe_execute(sql, (project_id,)) or []

    wb = Workbook()
    ws = wb.active
    ws.title = "Bookings"
    ws.append(["ID", "Date", "Time", "Service", "Client", "Phone", "Details"])

    for r in rows:
        ws.append([
            r["booking_id"], r["date"], r["time"],
            r["service"], r["client_name"], r["phone"], r["details"]
        ])

    return wb


# ─────────────────── helpers ───────────────────
def get_client_by_user(project_id: int, user_id: int):
    """Вернуть запись из clients по Telegram-ID."""
    rows = safe_execute(
        "SELECT * FROM clients WHERE project_id=? AND user_id=?",
        (project_id, user_id)
    )
    return rows[0] if rows else None


def get_free_slots_by_date(project_id: int, date: str):
    """
    Возвращает только свободные слоты (те, у которых нет записи в bookings).
    Каждый элемент — sqlite3.Row с полями: id, time.
    """
    rows = safe_execute(
        """
        SELECT wi.id, wi.time
          FROM work_intervals wi
     LEFT JOIN bookings b
            ON wi.id = b.slot_id
           AND wi.project_id = b.project_id
         WHERE wi.project_id = ?
           AND wi.date = ?
           AND b.id IS NULL
      ORDER BY wi.time
        """,
        (project_id, date)
    )
    return rows or []


# --- при желании можно добавить ещё поддерку конкретного слота ---

DayStat = namedtuple("DayStat", ["total", "booked", "past"])


# ─────────────────── clients helpers ───────────────────
def add_client(project_id: int, user_id: int, name: str, phone: str):
    """
    Создаёт клиента или обновляет его данные, если запись уже есть.
    Возвращает id клиента.
    """
    safe_execute("""
        INSERT INTO clients (project_id, user_id, name, phone)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(project_id, user_id) DO UPDATE
            SET name  = excluded.name,
                phone = excluded.phone
    """, (project_id, user_id, name, phone))  # upsert: ON CONFLICT DO UPDATE
    row = safe_execute(
        "SELECT id FROM clients WHERE project_id=? AND user_id=?",
        (project_id, user_id)
    )
    return row[0]["id"] if row else None


def get_booking_by_slot(project_id: int, slot_id: int):
    """
    Возвращает запись бронирования вместе с именем клиента и названием услуги,
    или None, если слот свободен.
    """
    sql = """
    SELECT
        b.id           AS booking_id,
        b.user_id      AS user_id,
        b.service_id   AS service_id,
        b.date         AS date,
        b.time         AS time,
        b.details      AS details,
        s.name         AS service_name,
        cl.name        AS client_name
    FROM bookings b
    JOIN services s ON b.service_id = s.id
    JOIN clients cl  ON b.user_id    = cl.user_id AND cl.project_id = b.project_id
    WHERE b.project_id = ? AND b.slot_id = ?
    """
    rows = safe_execute(sql, (project_id, slot_id))
    return rows[0] if rows else None


def update_client(project_id: int, client_id: int, *, name: str | None = None,
                  phone: str | None = None):
    """Частичное обновление данных клиента."""
    fields, params = [], []
    if name is not None: fields.append("name=?");  params.append(name)
    if phone is not None: fields.append("phone=?"); params.append(phone)
    if not fields:  # ничего менять не попросили
        return 0
    params.extend([project_id, client_id])
    sql = f"UPDATE clients SET {', '.join(fields)} WHERE project_id=? AND id=?"
    return safe_execute(sql, tuple(params))


def get_month_stats(project_id: int, year: int, month: int) -> dict[date, DayStat]:
    """
    Возвращает словарь {дата: DayStat(total_slots, booked_slots, past)},
    где:
      - total_slots  = общее число work_intervals в этот день,
      - booked_slots = число записей в bookings на эти слоты,
      - past         = True, если день < today.
    """
    # 1) Определяем границы месяца
    first = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    last = date(year, month, last_day)

    # 2) Собираем агрегацию из work_intervals + bookings
    sql = """
    SELECT
      w.date              AS day,
      COUNT(w.id)         AS total,
      COUNT(b.id)         AS booked
    FROM work_intervals w
    LEFT JOIN bookings b
      ON b.slot_id = w.id
    WHERE w.project_id = ?
      AND w.date BETWEEN ? AND ?
    GROUP BY day
    """
    rows = safe_execute(sql, (project_id, first.isoformat(), last.isoformat()))  # :contentReference[oaicite:0]{index=0}

    # 3) Переводим в DayStat и помечаем прошлое
    stats = {}
    today = date.today()
    for r in rows or []:
        d = datetime.fromisoformat(r["day"]).date()
        stats[d] = DayStat(
            total=r["total"],
            booked=r["booked"],
            past=d < today
        )

    # 4) Добавляем дни, где слотов нет (total=0)
    for day in range(1, last_day + 1):
        d = date(year, month, day)
        if d not in stats:
            stats[d] = DayStat(0, 0, d < today)

    return stats


def get_slot(project_id: int, slot_id: int):
    """
    Возвращает конкретный слот по ID (sqlite3.Row).
    """
    rows = safe_execute(
        "SELECT * FROM work_intervals WHERE project_id=? AND id=?",
        (project_id, slot_id)
    )
    return rows[0] if rows else None


def safe_execute(query: str, params: tuple = ()):
    """Выполнить SQL-запрос с обработкой ошибок."""
    try:
        cur.execute(query, params)
        if query.strip().upper().startswith("SELECT"):
            return cur.fetchall()
        else:
            conn.commit()
            if query.strip().upper().startswith("INSERT"):
                # для INSERT OR IGNORE теперь возвращаем rowcount:
                return cur.rowcount  # 1 если вставлено, 0 если проигнорировано
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
    slot = safe_execute("SELECT id FROM work_intervals WHERE project_id=? AND date=? AND time=?",
                        (project_id, date, time))
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
    """
    Безопасно создаёт новую бронь и при необходимости резервирует
    последующие слоты в соответствии с длительностью услуги.
    Возвращает ID первой записи в bookings или None.
    """
    try:
        cur.execute("BEGIN")
        # 1) Получаем дату и время слота по его ID
        cur.execute(
            "SELECT date, time FROM work_intervals "
            "WHERE project_id=? AND id=?",
            (project_id, slot_id)
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            return None
        slot_date, slot_time = row["date"], row["time"]

        # 2) Получаем длительность услуги (в 15-мин ячейках)
        cur.execute(
            "SELECT duration FROM services "
            "WHERE project_id=? AND id=?",
            (project_id, service_id)
        )
        svc = cur.fetchone()
        duration_cells = svc and svc["duration"] or 1

        # 3) Пытаемся вставить бронь на первый слот
        try:
            cur.execute(
                "INSERT INTO bookings(project_id, user_id, service_id, slot_id, date, time, details) "
                "VALUES(?,?,?,?,?,?,?)",
                (project_id, user_id, service_id, slot_id, slot_date, slot_time, details)
            )
        except sqlite3.IntegrityError:
            conn.rollback()
            return None  # слот уже занят

        booking_id = cur.lastrowid

        # 4) Резервируем последующие слоты (если duration_cells > 1)
        from datetime import datetime, timedelta
        base_dt = datetime.fromisoformat(f"{slot_date}T{slot_time}")
        for i in range(1, duration_cells):
            next_dt = base_dt + timedelta(minutes=15 * i)
            next_time = next_dt.strftime("%H:%M")
            # ищем ID интервала
            cur.execute(
                "SELECT id FROM work_intervals "
                "WHERE project_id=? AND date=? AND time=?",
                (project_id, slot_date, next_time)
            )
            nxt = cur.fetchone()
            if not nxt:
                # если слот не существует — откатываем и считаем бронь неуспешной
                conn.rollback()
                return None
            next_slot_id = nxt["id"]
            # пытаемся вставить «дополнительную» бронь, привязав детали к первому
            cur.execute(
                "INSERT INTO bookings(project_id, user_id, service_id, slot_id, date, time, details) "
                "VALUES(?,?,?,?,?,?,?)",
                (project_id, user_id, service_id, next_slot_id, slot_date, next_time, f"{details} (продолжение)")
            )

        # 5) Убедимся, что у клиента есть запись в clients
        cur.execute(
            "INSERT INTO clients(project_id, user_id) VALUES(?,?) "
            "ON CONFLICT(project_id, user_id) DO NOTHING",
            (project_id, user_id)
        )

        conn.commit()
        return booking_id

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
