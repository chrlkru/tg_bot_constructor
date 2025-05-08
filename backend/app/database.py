# app/database.py

import sqlite3
import json
import os
import json
from app.utils.db_safe import transaction
from pathlib import Path
from datetime import datetime, timedelta

from app.utils.db_safe import transaction, safe_execute

DB_PATH = Path(__file__).resolve().parent / "database.db"
SLOT_SIZE_MIN = 15  # минута ячейки для расписания

def init_db():
    with transaction(DB_PATH) as conn:
        cur = conn.cursor()
        # Проекты
        cur.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            template_type TEXT,
            description TEXT,
            token TEXT,
            content TEXT
        )
        """)
        # Каталог товаров/услуг
        cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            name TEXT,
            short_desc TEXT,
            full_desc TEXT,
            media_path TEXT
        )
        """)
        # Бронирования
        cur.execute("""
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
        )
        """)
        # Бан-лист
        cur.execute("""
        CREATE TABLE IF NOT EXISTS banned_users (
            project_id INTEGER,
            user_id INTEGER,
            PRIMARY KEY(project_id, user_id)
        )
        """)
        # Корзина
        cur.execute("""
        CREATE TABLE IF NOT EXISTS cart_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            user_id INTEGER,
            product_id INTEGER,
            quantity INTEGER DEFAULT 1
        )
        """)
        # Окна работы
        cur.execute("""
        CREATE TABLE IF NOT EXISTS work_intervals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            start_dt TEXT,
            end_dt TEXT
        )
        """)
        # Исключения (паника)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS work_exceptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            start_dt TEXT,
            end_dt TEXT,
            state TEXT
        )
        """)
        # Настройки рассылки
        cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)
        cur.executemany("""
            INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)
        """, [
            ('summary_enabled', 'true'),
            ('summary_time',    '07:00'),
            ('summary_timezone','Europe/Bucharest'),
        ])
        # FAQ
        cur.execute("""
        CREATE TABLE IF NOT EXISTS faq_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            question TEXT,
            answer TEXT,
            media_path TEXT
        )
        """)
        # Helper-bot: «пасты»
        cur.execute("""
        CREATE TABLE IF NOT EXISTS helper_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            alias TEXT UNIQUE,
            content TEXT,
            media_path TEXT
        )
        """)
        # Moderator-bot: настройки
        cur.execute("""
        CREATE TABLE IF NOT EXISTS moderation_settings (
            project_id    INTEGER PRIMARY KEY,
            allow_media    INTEGER DEFAULT 0,
            allow_stickers INTEGER DEFAULT 0,
            censor_enabled INTEGER DEFAULT 1,
            flood_max      INTEGER DEFAULT 3,
            flood_window_s INTEGER DEFAULT 600
        )
        """)
        # Moderator-bot: белый список доменов
        cur.execute("""
        CREATE TABLE IF NOT EXISTS link_whitelist (
            project_id INTEGER,
            domain     TEXT,
            PRIMARY KEY(project_id, domain)
        )
        """)
        # Moderator-bot: предупреждения (страйки)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_warnings (
            project_id INTEGER,
            chat_id    INTEGER,
            user_id    INTEGER,
            strikes    INTEGER DEFAULT 0,
            last_ts    INTEGER,
            PRIMARY KEY(project_id, chat_id, user_id)
        )
        """)
        # Moderator-bot: логирование нарушений
        cur.execute("""
        CREATE TABLE IF NOT EXISTS moderation_logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            chat_id    INTEGER,
            user_id    INTEGER,
            message_id INTEGER,
            violation  TEXT,
            text       TEXT,
            ts         INTEGER
        )
        """)
 # Anonymous‑Feedback: лог и бан‑лист
        cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback_messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  INTEGER,
            user_id     INTEGER,
            direction   TEXT,          -- 'in' | 'out'
            text        TEXT,
            ts          INTEGER
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback_blocked (
            project_id INTEGER,
            user_id    INTEGER,
            PRIMARY KEY(project_id, user_id)
        )
        """)
def create_project(project):
    with transaction(DB_PATH) as conn:
        cur = conn.execute(
            "INSERT INTO projects(name,template_type,description,token,content) VALUES(?,?,?,?,?)",
            (
                project.name,
                project.template_type,
                project.description,
                project.token,
                json.dumps(project.content)
            )
        )
        return cur.lastrowid
def update_project_content(project_id: int, content: dict):
    with transaction(DB_PATH) as conn:
        conn.execute(
            "UPDATE projects SET content=? WHERE id=?",
            (json.dumps(content), project_id)
        )
def get_projects(project_id=None):
    if project_id is not None:
        rows = safe_execute(
            "SELECT id,name,template_type,description,token,content FROM projects WHERE id=?",
            (project_id,),
            DB_PATH
        )
        if not rows:
            return None
        r = rows[0]
        return {
            "id":            r[0],
            "name":          r[1],
            "template_type": r[2],
            "description":   r[3],
            "token":         r[4],
            "content":       json.loads(r[5])
        }
    else:
        rows = safe_execute(
            "SELECT id,name,template_type,description,token,content FROM projects",
            (),
            DB_PATH
        )
        return [
            {
              "id":            r[0],
              "name":          r[1],
              "template_type": r[2],
              "description":   r[3],
              "token":         r[4],
              "content":       json.loads(r[5])
            }
            for r in rows
        ]

def get_products_list(project_id):
    rows = safe_execute(
        "SELECT id,name,short_desc,full_desc,media_path FROM products WHERE project_id=? ORDER BY id",
        (project_id,),
        DB_PATH
    )
    return [
        {"id": r[0], "name": r[1], "short_desc": r[2], "full_desc": r[3], "media": r[4] or ""}
        for r in rows
    ]

def add_product(project_id, name, short_desc, full_desc, media_path=""):
    with transaction(DB_PATH) as conn:
        cur = conn.execute(
            "INSERT INTO products(project_id,name,short_desc,full_desc,media_path) VALUES(?,?,?,?,?)",
            (project_id, name, short_desc, full_desc, media_path)
        )
        return cur.lastrowid

def delete_product(project_id, product_id):
    with transaction(DB_PATH) as conn:
        conn.execute(
            "DELETE FROM products WHERE project_id=? AND id=?",
            (project_id, product_id)
        )

def create_booking(project_id, user_id, service_id, start_dt, duration_cells, client_name, client_phone):
    with transaction(DB_PATH) as conn:
        cur = conn.execute(
            "INSERT INTO bookings(project_id,user_id,service_id,start_dt,duration_cells,client_name,client_phone) "
            "VALUES(?,?,?,?,?,?,?)",
            (project_id, user_id, service_id, start_dt, duration_cells, client_name, client_phone)
        )
        return cur.lastrowid

def get_booking(booking_id):
    rows = safe_execute(
        "SELECT project_id,user_id,service_id,start_dt,duration_cells,client_name,client_phone,status "
        "FROM bookings WHERE id=?",
        (booking_id,),
        DB_PATH
    )
    if not rows:
        return None
    r = rows[0]
    return {
        "project_id":     r[0],
        "user_id":        r[1],
        "service_id":     r[2],
        "start_dt":       r[3],
        "duration_cells": r[4],
        "client_name":    r[5],
        "client_phone":   r[6],
        "status":         r[7]
    }

def update_booking_status(booking_id, status):
    with transaction(DB_PATH) as conn:
        conn.execute(
            "UPDATE bookings SET status=? WHERE id=?",
            (status, booking_id)
        )

def get_bookings_by_date(project_id, date_str, status="confirmed"):
    rows = safe_execute(
        "SELECT id,user_id,service_id,start_dt,duration_cells,client_name,client_phone "
        "FROM bookings WHERE project_id=? AND status=? AND substr(start_dt,1,10)=? ORDER BY start_dt",
        (project_id, status, date_str),
        DB_PATH
    )
    return [
        {
          "id":              r[0],
          "user_id":         r[1],
          "service_id":      r[2],
          "start_dt":        r[3],
          "duration_cells":  r[4],
          "client_name":     r[5],
          "client_phone":    r[6]
        }
        for r in rows
    ]

def get_confirmed_future_bookings(project_id):
    now = datetime.utcnow().isoformat()
    rows = safe_execute(
        "SELECT id,start_dt,duration_cells,service_id,client_name "
        "FROM bookings WHERE project_id=? AND status='confirmed' AND start_dt>?",
        (project_id, now),
        DB_PATH
    )
    return [
        {"id": r[0], "start_dt": r[1], "duration_cells": r[2], "service_id": r[3], "client_name": r[4]}
        for r in rows
    ]

def get_all_bookings(project_id):
    rows = safe_execute(
        "SELECT id,service_id,start_dt,client_name,status "
        "FROM bookings WHERE project_id=?",
        (project_id,),
        DB_PATH
    )
    return [
        {"id": r[0], "service_id": r[1], "start_dt": r[2], "client_name": r[3], "status": r[4]}
        for r in rows
    ]

def add_work_interval(project_id, start_iso, end_iso):
    with transaction(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO work_intervals(project_id,start_dt,end_dt) VALUES(?,?,?)",
            (project_id, start_iso, end_iso)
        )

def get_work_intervals(project_id, days_ahead):
    now = datetime.utcnow()
    end = now + timedelta(days=days_ahead)
    rows = safe_execute(
        "SELECT id,start_dt,end_dt FROM work_intervals "
        "WHERE project_id=? AND start_dt>=? AND start_dt<=? ORDER BY start_dt",
        (project_id, now.isoformat(), end.isoformat()),
        DB_PATH
    )
    return [{"id": r[0], "start_dt": r[1], "end_dt": r[2]} for r in rows]

def delete_work_interval(interval_id):
    with transaction(DB_PATH) as conn:
        conn.execute("DELETE FROM work_intervals WHERE id=?", (interval_id,))

def add_work_exception(project_id, start_iso, end_iso, state):
    with transaction(DB_PATH) as conn:
        cur = conn.execute(
            "INSERT INTO work_exceptions(project_id,start_dt,end_dt,state) VALUES(?,?,?,?)",
            (project_id, start_iso, end_iso, state)
        )
        return cur.lastrowid

def get_planned_exceptions(project_id):
    rows = safe_execute(
        "SELECT id,start_dt FROM work_exceptions WHERE project_id=? AND state='planned'",
        (project_id,),
        DB_PATH
    )
    return [{"id": r[0], "start_dt": r[1]} for r in rows]

def activate_planned_exception(exception_id):
    with transaction(DB_PATH) as conn:
        conn.execute(
            "UPDATE work_exceptions SET state='active' WHERE id=?",
            (exception_id,)
        )
        row = conn.execute(
            "SELECT start_dt,end_dt FROM work_exceptions WHERE id=?", (exception_id,)
        ).fetchone()
        return row

def cancel_bookings_in_interval(project_id, start_iso, end_iso):
    with transaction(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id,user_id,service_id,start_dt FROM bookings "
            "WHERE project_id=? AND status='confirmed' AND start_dt>=? AND start_dt<=?",
            (project_id, start_iso, end_iso)
        ).fetchall()
        conn.execute(
            "UPDATE bookings SET status='cancelled_by_provider' "
            "WHERE project_id=? AND status='confirmed' AND start_dt>=? AND start_dt<=?",
            (project_id, start_iso, end_iso)
        )
        return [
            {"id": r[0], "user_id": r[1], "service_id": r[2], "start_dt": r[3]}
            for r in rows
        ]

def get_setting(key):
    rows = safe_execute(
        "SELECT value FROM settings WHERE key=?",
        (key,),
        DB_PATH
    )
    return rows[0][0] if rows else None

def set_setting(key, value):
    with transaction(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value)
        )

def ban_user(project_id, user_id):
    with transaction(DB_PATH) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO banned_users(project_id,user_id) VALUES(?,?)",
            (project_id, user_id)
        )

def is_banned(project_id, user_id):
    rows = safe_execute(
        "SELECT 1 FROM banned_users WHERE project_id=? AND user_id=?",
        (project_id, user_id),
        DB_PATH
    )
    return bool(rows)

def add_to_cart(project_id, user_id, product_id, quantity=1):
    with transaction(DB_PATH) as conn:
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

def get_cart_items(project_id, user_id):
    rows = safe_execute(
        "SELECT ci.id,ci.product_id,ci.quantity,p.name,p.full_desc,p.media_path "
        "FROM cart_items ci JOIN products p ON p.id=ci.product_id "
        "WHERE ci.project_id=? AND ci.user_id=? ORDER BY ci.id",
        (project_id, user_id),
        DB_PATH
    )
    return [
        {
          "cart_id":   r[0],
          "product_id":r[1],
          "quantity":  r[2],
          "name":      r[3],
          "full_desc": r[4],
          "media":     r[5] or ""
        }
        for r in rows
    ]

def update_cart_item(cart_id, new_quantity):
    with transaction(DB_PATH) as conn:
        if new_quantity > 0:
            conn.execute(
                "UPDATE cart_items SET quantity=? WHERE id=?", (new_quantity, cart_id)
            )
        else:
            conn.execute(
                "DELETE FROM cart_items WHERE id=?", (cart_id,)
            )

def delete_cart_item(cart_id):
    with transaction(DB_PATH) as conn:
        conn.execute("DELETE FROM cart_items WHERE id=?", (cart_id,))

def clear_cart(project_id, user_id):
    with transaction(DB_PATH) as conn:
        conn.execute(
            "DELETE FROM cart_items WHERE project_id=? AND user_id=?", (project_id, user_id)
        )

def get_faq_entries(project_id):
    rows = safe_execute(
        "SELECT id,question,answer,media_path FROM faq_entries WHERE project_id=? ORDER BY id",
        (project_id,),
        DB_PATH
    )
    return [
        {"id": r[0], "question": r[1], "answer": r[2], "media": r[3] or ""}
        for r in rows
    ]

def add_faq_entry(project_id, question, answer, media_path=""):
    with transaction(DB_PATH) as conn:
        cur = conn.execute(
            "INSERT INTO faq_entries(project_id,question,answer,media_path) VALUES(?,?,?,?)",
            (project_id, question, answer, media_path)
        )
        return cur.lastrowid

def delete_faq_entry(project_id, entry_id):
    with transaction(DB_PATH) as conn:
        conn.execute(
            "DELETE FROM faq_entries WHERE project_id=? AND id=?", (project_id, entry_id)
        )
