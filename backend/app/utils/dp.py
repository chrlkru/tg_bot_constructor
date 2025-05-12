# utils/dp.py
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH = Path(__file__).resolve().parent / "database.db"
SLOT_SIZE_MIN = 15  # минута «ячейки» для Smart-Booking

@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """Создаёт все таблицы, нужные для работы всех шаблонов."""
    with _conn() as db:
        # --- OrderBot ---
        db.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            name TEXT,
            short_desc TEXT,
            full_desc TEXT,
            media_path TEXT
        )""")
        db.execute("""
        CREATE TABLE IF NOT EXISTS cart_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            user_id INTEGER,
            product_id INTEGER,
            quantity INTEGER DEFAULT 1
        )""")
        db.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            user_id INTEGER,
            product TEXT,
            quantity INTEGER,
            address TEXT,
            media_path TEXT
        )""")
        db.execute("""
        CREATE TABLE IF NOT EXISTS banned_users (
            project_id INTEGER,
            user_id    INTEGER,
            PRIMARY KEY(project_id,user_id)
        )""")
        # --- FAQBot ---
        db.execute("""
        CREATE TABLE IF NOT EXISTS faq_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            question TEXT,
            answer TEXT,
            media_path TEXT
        )""")
        # --- HelperBot ---
        db.execute("""
        CREATE TABLE IF NOT EXISTS helper_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            alias TEXT,
            content TEXT,
            media_path TEXT
        )""")
        # --- FeedbackBot ---
        db.execute("""
        CREATE TABLE IF NOT EXISTS feedback_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            user_id INTEGER,
            direction TEXT,
            text TEXT,
            ts INTEGER
        )""")
        db.execute("""
        CREATE TABLE IF NOT EXISTS feedback_blocked (
            project_id INTEGER,
            user_id INTEGER,
            PRIMARY KEY(project_id, user_id)
        )""")
        # --- ModeratorBot ---
        db.execute("""
        CREATE TABLE IF NOT EXISTS moderation_settings (
            project_id INTEGER PRIMARY KEY,
            allow_media    INTEGER DEFAULT 0,
            allow_stickers INTEGER DEFAULT 0,
            censor_enabled INTEGER DEFAULT 1,
            flood_max      INTEGER DEFAULT 3,
            flood_window_s INTEGER DEFAULT 600
        )""")
        db.execute("""
        CREATE TABLE IF NOT EXISTS link_whitelist (
            project_id INTEGER,
            domain     TEXT,
            PRIMARY KEY(project_id, domain)
        )""")
        db.execute("""
        CREATE TABLE IF NOT EXISTS user_warnings (
            project_id INTEGER,
            chat_id    INTEGER,
            user_id    INTEGER,
            strikes    INTEGER DEFAULT 0,
            last_ts    INTEGER,
            PRIMARY KEY(project_id, chat_id, user_id)
        )""")
        db.execute("""
        CREATE TABLE IF NOT EXISTS moderation_logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            chat_id    INTEGER,
            user_id    INTEGER,
            message_id INTEGER,
            violation  TEXT,
            text       TEXT,
            ts         INTEGER
        )""")
        # --- SmartBookingCRM ---
        db.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            name TEXT,
            duration_cells INTEGER,
            price REAL
        )""")
        db.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            user_id INTEGER,
            service_id INTEGER,
            start_dt TEXT,
            duration_cells INTEGER,
            client_name TEXT,
            client_phone TEXT,
            status TEXT DEFAULT 'pending',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        db.execute("""
        CREATE TABLE IF NOT EXISTS work_intervals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            start_dt TEXT,
            end_dt TEXT
        )""")
        db.execute("""
        CREATE TABLE IF NOT EXISTS work_exceptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            start_dt TEXT,
            end_dt TEXT,
            status TEXT
        )""")
        # --- Settings (для SmartBooking summary) ---
        db.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            project_id INTEGER,
            key TEXT,
            value TEXT,
            PRIMARY KEY(project_id, key)
        )""")
        # --- QuizBot ---
        db.execute("""
        CREATE TABLE IF NOT EXISTS quiz_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            text TEXT,
            options_json TEXT
        )""")

# ----------------------------------------------------------------------------
# 1) OrderBot CRUD
# ----------------------------------------------------------------------------
def get_products_list(project_id: int):
    with _conn() as db:
        cur = db.execute(
            "SELECT id,name,short_desc,full_desc,media_path "
            "FROM products WHERE project_id=? ORDER BY id",
            (project_id,)
        )
        return [
            {"id": r["id"], "name": r["name"],
             "short_desc": r["short_desc"], "full_desc": r["full_desc"],
             "media": r["media_path"] or ""}
            for r in cur.fetchall()
        ]

def add_product(project_id: int, name: str, short_desc: str,
                full_desc: str, media_path: str = "") -> int:
    with _conn() as db:
        cur = db.execute(
            "INSERT INTO products(project_id,name,short_desc,full_desc,media_path) "
            "VALUES(?,?,?,?,?)",
            (project_id, name, short_desc, full_desc, media_path)
        )
        return cur.lastrowid

def delete_product(project_id: int, product_id: int):
    with _conn() as db:
        db.execute(
            "DELETE FROM products WHERE project_id=? AND id=?",
            (project_id, product_id)
        )

def add_to_cart(project_id: int, user_id: int, product_id: int, quantity: int = 1):
    with _conn() as db:
        row = db.execute(
            "SELECT id,quantity FROM cart_items "
            "WHERE project_id=? AND user_id=? AND product_id=?",
            (project_id, user_id, product_id)
        ).fetchone()
        if row:
            db.execute(
                "UPDATE cart_items SET quantity=? WHERE id=?",
                (row["quantity"]+quantity, row["id"])
            )
        else:
            db.execute(
                "INSERT INTO cart_items(project_id,user_id,product_id,quantity) "
                "VALUES(?,?,?,?)",
                (project_id, user_id, product_id, quantity)
            )

def get_cart_items(project_id: int, user_id: int):
    with _conn() as db:
        cur = db.execute(
            "SELECT ci.id AS cart_id, ci.product_id, ci.quantity, "
            "       p.name, p.full_desc, p.media_path "
            "FROM cart_items ci "
            "JOIN products p ON p.id=ci.product_id "
            "WHERE ci.project_id=? AND ci.user_id=? ORDER BY ci.id",
            (project_id, user_id)
        )
        return [
            {"cart_id": r["cart_id"], "product_id": r["product_id"],
             "quantity": r["quantity"], "name": r["name"],
             "full_desc": r["full_desc"], "media": r["media_path"] or ""}
            for r in cur.fetchall()
        ]

def update_cart_item(cart_id: int, new_qty: int):
    with _conn() as db:
        if new_qty > 0:
            db.execute(
                "UPDATE cart_items SET quantity=? WHERE id=?",
                (new_qty, cart_id)
            )
        else:
            db.execute("DELETE FROM cart_items WHERE id=?", (cart_id,))

def delete_cart_item(cart_id: int):
    with _conn() as db:
        db.execute("DELETE FROM cart_items WHERE id=?", (cart_id,))

def clear_cart(project_id: int, user_id: int):
    with _conn() as db:
        db.execute(
            "DELETE FROM cart_items WHERE project_id=? AND user_id=?",
            (project_id, user_id)
        )

def save_order(o: dict):
    with _conn() as db:
        db.execute(
            "INSERT INTO orders("
            " project_id,user_id,product,quantity,address,media_path"
            ") VALUES(?,?,?,?,?,?)",
            (o["project_id"], o["user_id"],
             o["product"], o["quantity"],
             o.get("address",""), o.get("media_path",""))
        )

def is_banned(project_id: int, user_id: int) -> bool:
    with _conn() as db:
        r = db.execute(
            "SELECT 1 FROM banned_users WHERE project_id=? AND user_id=?",
            (project_id, user_id)
        ).fetchone()
        return bool(r)

# ----------------------------------------------------------------------------
# 2) FAQBot CRUD
# ----------------------------------------------------------------------------
def get_faq_entries(project_id: int):
    with _conn() as db:
        cur = db.execute(
            "SELECT id,question,answer,media_path "
            "FROM faq_entries WHERE project_id=? ORDER BY id",
            (project_id,)
        )
        return [
            {"id": r["id"], "question": r["question"],
             "answer": r["answer"], "media": r["media_path"] or ""}
            for r in cur.fetchall()
        ]

def add_faq_entry(project_id: int, question: str, answer: str, media_path: str = "") -> int:
    with _conn() as db:
        cur = db.execute(
            "INSERT INTO faq_entries(project_id,question,answer,media_path) "
            "VALUES(?,?,?,?)",
            (project_id, question, answer, media_path)
        )
        return cur.lastrowid

def delete_faq_entry(project_id: int, entry_id: int):
    with _conn() as db:
        db.execute(
            "DELETE FROM faq_entries WHERE project_id=? AND id=?",
            (project_id, entry_id)
        )

# ----------------------------------------------------------------------------
# 3) HelperBot CRUD
# ----------------------------------------------------------------------------
def add_helper_entry(project_id: int, alias: str, content: str, media_path: str = "") -> int:
    with _conn() as db:
        cur = db.execute(
            "INSERT INTO helper_entries(project_id,alias,content,media_path) "
            "VALUES(?,?,?,?)",
            (project_id, alias, content, media_path)
        )
        return cur.lastrowid

def get_helper_by_alias(project_id: int, alias: str):
    with _conn() as db:
        return db.execute(
            "SELECT content,media_path FROM helper_entries "
            "WHERE project_id=? AND alias=?",
            (project_id, alias)
        ).fetchone()

def get_all_helper_entries(project_id: int):
    with _conn() as db:
        return [
            {"id": r["id"], "alias": r["alias"],
             "content": r["content"], "media": r["media_path"] or ""}
            for r in db.execute(
                "SELECT id,alias,content,media_path FROM helper_entries "
                "WHERE project_id=? ORDER BY id",
                (project_id,)
            ).fetchall()
        ]

def delete_helper_entry(project_id: int, entry_id: int):
    with _conn() as db:
        db.execute(
            "DELETE FROM helper_entries WHERE project_id=? AND id=?",
            (project_id, entry_id)
        )

# ----------------------------------------------------------------------------
# 4) FeedbackBot CRUD
# ----------------------------------------------------------------------------
def log_feedback(project_id: int, user_id: int, direction: str, text: str):
    ts = int(datetime.utcnow().timestamp())
    with _conn() as db:
        db.execute(
            "INSERT INTO feedback_messages(project_id,user_id,direction,text,ts) "
            "VALUES(?,?,?,?,?)",
            (project_id, user_id, direction, text, ts)
        )

def block_feedback_user(project_id: int, user_id: int):
    with _conn() as db:
        db.execute(
            "INSERT OR IGNORE INTO feedback_blocked(project_id,user_id) VALUES(?,?)",
            (project_id, user_id)
        )

def is_feedback_blocked(project_id: int, user_id: int) -> bool:
    with _conn() as db:
        r = db.execute(
            "SELECT 1 FROM feedback_blocked WHERE project_id=? AND user_id=?",
            (project_id, user_id)
        ).fetchone()
        return bool(r)

# ----------------------------------------------------------------------------
# 5) ModeratorBot CRUD
# ----------------------------------------------------------------------------
def toggle_moderation_setting(project_id: int, key: str, val: int):
    with _conn() as db:
        db.execute(f"""
            INSERT INTO moderation_settings(project_id,{key})
            VALUES(?,?)
            ON CONFLICT(project_id) DO UPDATE SET {key}=excluded.{key}
        """, (project_id, val))

def whitelist_add(project_id: int, domain: str):
    with _conn() as db:
        db.execute(
            "INSERT OR IGNORE INTO link_whitelist(project_id,domain) VALUES(?,?)",
            (project_id, domain.lower())
        )

# ----------------------------------------------------------------------------
# 6) SmartBookingCRM CRUD
# ----------------------------------------------------------------------------
def add_service(project_id: int, name: str, duration_cells: int, price: float = None) -> int:
    with _conn() as db:
        cur = db.execute(
            "INSERT INTO services(project_id,name,duration_cells,price) VALUES(?,?,?,?)",
            (project_id, name, duration_cells, price)
        )
        return cur.lastrowid

def get_services(project_id: int):
    with _conn() as db:
        return [
            {"id": r["id"], "name": r["name"],
             "duration_cells": r["duration_cells"], "price": r["price"]}
            for r in db.execute(
                "SELECT id,name,duration_cells,price FROM services WHERE project_id=? ORDER BY id",
                (project_id,)
            ).fetchall()
        ]

def delete_service(project_id: int, service_id: int):
    with _conn() as db:
        db.execute(
            "DELETE FROM services WHERE project_id=? AND id=?",
            (project_id, service_id)
        )

def create_booking(project_id: int, user_id: int, service_id: int,
                   start_dt: str, duration_cells: int,
                   client_name: str, client_phone: str) -> int:
    with _conn() as db:
        cur = db.execute(
            "INSERT INTO bookings("
            " project_id,user_id,service_id,start_dt,"
            " duration_cells,client_name,client_phone"
            ") VALUES(?,?,?,?,?,?,?)",
            (project_id, user_id, service_id, start_dt,
             duration_cells, client_name, client_phone)
        )
        return cur.lastrowid

def get_bookings_by_date(project_id: int, date_str: str, status: str="pending"):
    with _conn() as db:
        return [
            {"id": r["id"], "user_id": r["user_id"],
             "service_id": r["service_id"], "start_dt": r["start_dt"],
             "duration_cells": r["duration_cells"],
             "client_name": r["client_name"], "client_phone": r["client_phone"]}
            for r in db.execute(
                "SELECT id,user_id,service_id,start_dt,duration_cells,client_name,client_phone "
                "FROM bookings WHERE project_id=? AND status=? AND "
                "substr(start_dt,1,10)=? ORDER BY start_dt",
                (project_id, status, date_str)
            ).fetchall()
        ]

def update_booking_status(booking_id: int, status: str):
    with _conn() as db:
        db.execute(
            "UPDATE bookings SET status=? WHERE id=?",
            (status, booking_id)
        )

def get_confirmed_future_bookings(project_id: int):
    cutoff = datetime.utcnow().isoformat()
    with _conn() as db:
        return [
            {"id": r["id"], "start_dt": r["start_dt"],
             "duration_cells": r["duration_cells"],
             "service_id": r["service_id"], "client_name": r["client_name"]}
            for r in db.execute(
                "SELECT id,start_dt,duration_cells,service_id,client_name "
                "FROM bookings WHERE project_id=? AND status='confirmed' AND start_dt>? ",
                (project_id, cutoff)
            ).fetchall()
        ]

def add_work_interval(project_id: int, start_dt: str, end_dt: str) -> int:
    with _conn() as db:
        cur = db.execute(
            "INSERT INTO work_intervals(project_id,start_dt,end_dt) VALUES(?,?,?)",
            (project_id, start_dt, end_dt)
        )
        return cur.lastrowid

def get_work_intervals(project_id: int):
    with _conn() as db:
        return [
            {"id": r["id"], "start_dt": r["start_dt"], "end_dt": r["end_dt"]}
            for r in db.execute(
                "SELECT id,start_dt,end_dt FROM work_intervals "
                "WHERE project_id=? ORDER BY start_dt",
                (project_id,)
            ).fetchall()
        ]

def delete_work_interval(interval_id: int):
    with _conn() as db:
        db.execute("DELETE FROM work_intervals WHERE id=?", (interval_id,))

def add_work_exception(project_id: int, start_dt: str, end_dt: str, status: str) -> int:
    with _conn() as db:
        cur = db.execute(
            "INSERT INTO work_exceptions(project_id,start_dt,end_dt,status) VALUES(?,?,?,?)",
            (project_id, start_dt, end_dt, status)
        )
        return cur.lastrowid

def get_planned_exceptions(project_id: int):
    with _conn() as db:
        return [
            {"id": r["id"], "start_dt": r["start_dt"],
             "end_dt": r["end_dt"], "status": r["status"]}
            for r in db.execute(
                "SELECT id,start_dt,end_dt,status FROM work_exceptions "
                "WHERE project_id=? ORDER BY start_dt",
                (project_id,)
            ).fetchall()
        ]

def cancel_bookings_in_interval(project_id: int, start_dt: str, end_dt: str):
    with _conn() as db:
        affected = db.execute(
            "SELECT id FROM bookings WHERE project_id=? AND start_dt>=? AND start_dt<=? AND status='confirmed'",
            (project_id, start_dt, end_dt)
        ).fetchall()
        db.execute(
            "UPDATE bookings SET status='cancelled_by_provider' "
            "WHERE project_id=? AND start_dt>=? AND start_dt<=? AND status='confirmed'",
            (project_id, start_dt, end_dt)
        )
        return [r["id"] for r in affected]

def set_setting(project_id: int, key: str, value: str):
    with _conn() as db:
        db.execute(
            "INSERT OR REPLACE INTO settings(project_id,key,value) VALUES(?,?,?)",
            (project_id, key, value)
        )

def get_setting(project_id: int, key: str) -> str | None:
    with _conn() as db:
        row = db.execute(
            "SELECT value FROM settings WHERE project_id=? AND key=?",
            (project_id, key)
        ).fetchone()
        return row["value"] if row else None

# ----------------------------------------------------------------------------
# 7) QuizBot CRUD
# ----------------------------------------------------------------------------
def add_quiz_question(project_id: int, text: str, options: list[str]) -> int:
    opts = json.dumps(options, ensure_ascii=False)
    with _conn() as db:
        cur = db.execute(
            "INSERT INTO quiz_questions(project_id,text,options_json) VALUES(?,?,?)",
            (project_id, text, opts)
        )
        return cur.lastrowid

def get_quiz_questions(project_id: int):
    with _conn() as db:
        return [
            {"id": r["id"], "text": r["text"], "options": json.loads(r["options_json"])}
            for r in db.execute(
                "SELECT id,text,options_json FROM quiz_questions WHERE project_id=? ORDER BY id",
                (project_id,)
            ).fetchall()
        ]

def delete_quiz_question(question_id: int):
    with _conn() as db:
        db.execute("DELETE FROM quiz_questions WHERE id=?", (question_id,))
