import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "database.db"

@contextmanager
def transaction():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def safe_execute(query: str, params: tuple = ()):
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(query, params)
        rows = cur.fetchall()
        return rows
    finally:
        conn.close()

def init_db():
    """Create all tables needed by the bots."""
    with transaction() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                name TEXT,
                short_desc TEXT,
                full_desc TEXT,
                media_path TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cart_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                user_id INTEGER,
                product_id INTEGER,
                quantity INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                user_id INTEGER,
                product TEXT,
                quantity INTEGER,
                address TEXT,
                media_path TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS faq_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                question TEXT,
                answer TEXT,
                media_path TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS helper_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                alias TEXT,
                content TEXT,
                media_path TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback_blocked (
                project_id INTEGER,
                user_id INTEGER,
                PRIMARY KEY(project_id, user_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                user_id INTEGER,
                direction TEXT,
                text TEXT,
                ts INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS banned_users (
                project_id INTEGER,
                user_id INTEGER,
                PRIMARY KEY(project_id, user_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                name TEXT,
                category TEXT,
                price INTEGER,
                duration_cells INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS work_intervals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                start_dt TEXT,
                end_dt TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS work_exceptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                start_dt TEXT,
                end_dt TEXT,
                status TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                user_id INTEGER,
                service_id INTEGER,
                start_dt TEXT,
                duration_cells INTEGER,
                client_name TEXT,
                client_phone TEXT,
                status TEXT DEFAULT 'confirmed'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                project_id INTEGER,
                key TEXT,
                value TEXT,
                PRIMARY KEY(project_id, key)
            )
        """)

# ——— Order / Cart ——————————————————————————————————————
def get_products_list(project_id: int):
    rows = safe_execute(
        "SELECT id,name,short_desc,full_desc,media_path "
        "FROM products WHERE project_id=? ORDER BY id",
        (project_id,)
    )
    return [
        {"id": r[0], "name": r[1], "short_desc": r[2], "full_desc": r[3], "media": r[4] or ""}
        for r in rows
    ]

def add_to_cart(project_id: int, user_id: int, product_id: int, quantity: int = 1):
    with transaction() as conn:
        cur = conn.execute(
            "SELECT id,quantity FROM cart_items WHERE project_id=? AND user_id=? AND product_id=?",
            (project_id, user_id, product_id)
        )
        row = cur.fetchone()
        if row:
            conn.execute(
                "UPDATE cart_items SET quantity=? WHERE id=?",
                (row[1] + quantity, row[0])
            )
        else:
            conn.execute(
                "INSERT INTO cart_items(project_id,user_id,product_id,quantity) VALUES(?,?,?,?)",
                (project_id, user_id, product_id, quantity)
            )

def get_cart_items(project_id: int, user_id: int):
    rows = safe_execute(
        "SELECT ci.id,ci.product_id,ci.quantity,p.name,p.full_desc,p.media_path "
        "FROM cart_items ci JOIN products p ON p.id=ci.product_id "
        "WHERE ci.project_id=? AND ci.user_id=? ORDER BY ci.id",
        (project_id, user_id)
    )
    return [
        {"cart_id": r[0], "product_id": r[1], "quantity": r[2],
         "name": r[3], "full_desc": r[4], "media": r[5] or ""}
        for r in rows
    ]

def update_cart_item(cart_id: int, quantity: int):
    with transaction() as conn:
        conn.execute(
            "UPDATE cart_items SET quantity=? WHERE id=?",
            (quantity, cart_id)
        )

def delete_cart_item(cart_id: int):
    with transaction() as conn:
        conn.execute(
            "DELETE FROM cart_items WHERE id=?",
            (cart_id,)
        )

def clear_cart(project_id: int, user_id: int):
    with transaction() as conn:
        conn.execute(
            "DELETE FROM cart_items WHERE project_id=? AND user_id=?",
            (project_id, user_id)
        )

def save_order(order: dict):
    with transaction() as conn:
        conn.execute(
            "INSERT INTO orders(project_id,user_id,product,quantity,address,media_path) "
            "VALUES(?,?,?,?,?,?)",
            (order["project_id"], order["user_id"],
             order["product"], order["quantity"],
             order["address"], order.get("media_path",""))
        )

# ——— FAQ —————————————————————————————————————————————
def get_faq_entries(project_id: int):
    rows = safe_execute(
        "SELECT id,question,answer,media_path FROM faq_entries WHERE project_id=? ORDER BY id",
        (project_id,)
    )
    return [
        {"id": r[0], "question": r[1], "answer": r[2], "media": r[3] or ""}
        for r in rows
    ]

def add_faq_entry(project_id: int, question: str, answer: str, media_path: str = ""):
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO faq_entries(project_id,question,answer,media_path) VALUES(?,?,?,?)",
            (project_id, question, answer, media_path)
        )
        return cur.lastrowid

def delete_faq_entry(project_id: int, entry_id: int):
    with transaction() as conn:
        conn.execute(
            "DELETE FROM faq_entries WHERE project_id=? AND id=?",
            (project_id, entry_id)
        )

# ——— Helper ——————————————————————————————————————————
def add_helper_entry(project_id: int, alias: str, content: str, media_path: str=""):
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO helper_entries(project_id,alias,content,media_path) VALUES(?,?,?,?)",
            (project_id, alias, content, media_path)
        )
        return cur.lastrowid

def get_helper_by_alias(project_id: int, alias: str):
    rows = safe_execute(
        "SELECT content,media_path FROM helper_entries WHERE project_id=? AND alias=?",
        (project_id, alias)
    )
    return rows[0] if rows else None

def get_all_helper_entries(project_id: int):
    rows = safe_execute(
        "SELECT id,alias,content,media_path FROM helper_entries WHERE project_id=? ORDER BY id",
        (project_id,)
    )
    return [
        {"id": r[0], "alias": r[1], "content": r[2], "media": r[3] or ""}
        for r in rows
    ]

def update_helper_entry(project_id: int, entry_id: int,
                        alias: str=None, content: str=None, media_path: str=None):
    fields, params = [], []
    if alias is not None:
        fields.append("alias=?");    params.append(alias)
    if content is not None:
        fields.append("content=?");  params.append(content)
    if media_path is not None:
        fields.append("media_path=?"); params.append(media_path)
    if not fields:
        return
    params.extend([project_id, entry_id])
    with transaction() as conn:
        conn.execute(
            f"UPDATE helper_entries SET {','.join(fields)} WHERE project_id=? AND id=?",
            tuple(params)
        )

def delete_helper_entry(project_id: int, entry_id: int):
    with transaction() as conn:
        conn.execute(
            "DELETE FROM helper_entries WHERE project_id=? AND id=?",
            (project_id, entry_id)
        )

# ——— Feedback —————————————————————————————————————————
def block_user(project_id: int, user_id: int):
    with transaction() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO feedback_blocked(project_id,user_id) VALUES(?,?)",
            (project_id, user_id)
        )

def is_blocked(project_id: int, user_id: int) -> bool:
    rows = safe_execute(
        "SELECT 1 FROM feedback_blocked WHERE project_id=? AND user_id=?",
        (project_id, user_id)
    )
    return bool(rows)

def log_feedback(project_id: int, user_id: int, direction: str, text: str):
    ts = int(__import__("time").time())
    with transaction() as conn:
        conn.execute(
            "INSERT INTO feedback_messages(project_id,user_id,direction,text,ts) VALUES(?,?,?,?,?)",
            (project_id, user_id, direction, text, ts)
        )

# ——— Moderator ———————————————————————————————————————
def ban_user(project_id: int, user_id: int):
    with transaction() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO banned_users(project_id,user_id) VALUES(?,?)",
            (project_id, user_id)
        )

def is_banned(project_id: int, user_id: int) -> bool:
    rows = safe_execute(
        "SELECT 1 FROM banned_users WHERE project_id=? AND user_id=?",
        (project_id, user_id)
    )
    return bool(rows)

# ——— Services ———————————————————————————————————————
def add_service(project_id: int, name: str, category: str, price: int, duration_cells: int) -> int:
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO services(project_id,name,category,price,duration_cells) VALUES(?,?,?,?,?)",
            (project_id, name, category, price, duration_cells)
        )
        return cur.lastrowid

def get_services(project_id: int):
    rows = safe_execute(
        "SELECT id,name,category,price,duration_cells FROM services WHERE project_id=? ORDER BY id",
        (project_id,)
    )
    return [
        {"id": r[0], "name": r[1], "category": r[2], "price": r[3], "duration_cells": r[4]}
        for r in rows
    ]

def delete_service(service_id: int):
    with transaction() as conn:
        conn.execute(
            "DELETE FROM services WHERE id=?",
            (service_id,)
        )

# ——— Work Intervals & Exceptions —————————————————————————
def add_work_interval(project_id: int, start_dt: str, end_dt: str):
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO work_intervals(project_id,start_dt,end_dt) VALUES(?,?,?)",
            (project_id, start_dt, end_dt)
        )
        return cur.lastrowid

def get_work_intervals(project_id: int, slot_size_min: int = None):
    rows = safe_execute(
        "SELECT id,start_dt,end_dt FROM work_intervals WHERE project_id=? ORDER BY start_dt",
        (project_id,)
    )
    return [{"id": r[0], "start_dt": r[1], "end_dt": r[2]} for r in rows]

def delete_work_interval(interval_id: int):
    with transaction() as conn:
        conn.execute(
            "DELETE FROM work_intervals WHERE id=?",
            (interval_id,)
        )

def add_work_exception(project_id: int, start_dt: str, end_dt: str, status: str) -> int:
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO work_exceptions(project_id,start_dt,end_dt,status) VALUES(?,?,?,?)",
            (project_id, start_dt, end_dt, status)
        )
        return cur.lastrowid

def cancel_bookings_in_interval(project_id: int, start_dt: str, end_dt: str):
    rows = safe_execute(
        "SELECT id FROM bookings WHERE project_id=? AND start_dt>=? AND start_dt<=?",
        (project_id, start_dt, end_dt)
    )
    ids = [r[0] for r in rows]
    with transaction() as conn:
        conn.execute(
            "UPDATE bookings SET status='cancelled' WHERE project_id=? AND start_dt>=? AND start_dt<=?",
            (project_id, start_dt, end_dt)
        )
    return ids

def get_planned_exceptions(project_id: int):
    rows = safe_execute(
        "SELECT id,start_dt,end_dt,status FROM work_exceptions WHERE project_id=? ORDER BY start_dt",
        (project_id,)
    )
    return [
        {"id": r[0], "start_dt": r[1], "end_dt": r[2], "status": r[3]}
        for r in rows
    ]

# ——— Bookings & Clients —————————————————————————————————
def create_booking(project_id: int, user_id: int, service_id: int,
                   start_dt: str, duration_cells: int,
                   client_name: str, client_phone: str) -> int:
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO bookings(project_id,user_id,service_id,start_dt,duration_cells,client_name,client_phone) "
            "VALUES(?,?,?,?,?,?,?)",
            (project_id, user_id, service_id, start_dt, duration_cells, client_name, client_phone)
        )
        return cur.lastrowid

create_booking_safe = create_booking

def get_booking(booking_id: int):
    rows = safe_execute(
        "SELECT id,project_id,user_id,service_id,start_dt,duration_cells,client_name,client_phone,status "
        "FROM bookings WHERE id=?",
        (booking_id,)
    )
    return dict(zip(
        ["id","project_id","user_id","service_id","start_dt","duration_cells","client_name","client_phone","status"],
        rows[0]
    )) if rows else None

def get_bookings_by_date(project_id: int, date_str: str, status: str="confirmed"):
    rows = safe_execute(
        "SELECT id,user_id,service_id,start_dt,duration_cells,client_name,client_phone "
        "FROM bookings WHERE project_id=? AND status=? AND substr(start_dt,1,10)=? ORDER BY start_dt",
        (project_id, status, date_str)
    )
    return [
        {"id": r[0], "user_id": r[1], "service_id": r[2],
         "start_dt": r[3], "duration_cells": r[4],
         "client_name": r[5], "client_phone": r[6]}
        for r in rows
    ]

def update_booking_status(booking_id: int, status: str):
    with transaction() as conn:
        conn.execute(
            "UPDATE bookings SET status=? WHERE id=?",
            (status, booking_id)
        )

def get_confirmed_future_bookings(project_id: int):
    now = __import__("datetime").datetime.utcnow().isoformat()
    rows = safe_execute(
        "SELECT id,start_dt,duration_cells,service_id,client_name "
        "FROM bookings WHERE project_id=? AND status='confirmed' AND start_dt>?",
        (project_id, now)
    )
    return [
        {"id": r[0], "start_dt": r[1], "duration_cells": r[2],
         "service_id": r[3], "client_name": r[4]}
        for r in rows
    ]

def get_all_clients(project_id: int):
    rows = safe_execute(
        "SELECT DISTINCT user_id,client_name,client_phone FROM bookings WHERE project_id=?",
        (project_id,)
    )
    return [
        {"user_id": r[0], "name": r[1], "phone": r[2]}
        for r in rows
    ]

def get_all_bookings(project_id: int):
    rows = safe_execute(
        "SELECT b.id, s.name, b.start_dt, b.client_name, b.status "
        "FROM bookings b JOIN services s ON b.service_id=s.id "
        "WHERE b.project_id=? ORDER BY b.id",
        (project_id,)
    )
    return [
        {"id": r[0], "service_name": r[1], "start_dt": r[2], "client_name": r[3], "status": r[4]}
        for r in rows
    ]

# ——— Settings ————————————————————————————————————————
def get_setting(project_id: int, key: str):
    rows = safe_execute(
        "SELECT value FROM settings WHERE project_id=? AND key=?",
        (project_id, key)
    )
    return rows[0][0] if rows else ""

def set_setting(project_id: int, key: str, value: str):
    with transaction() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings(project_id,key,value) VALUES(?,?,?)",
            (project_id, key, value)
        )
