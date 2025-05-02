import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH = Path(__file__).resolve().parent / "database.db"
SLOT_SIZE_MIN = 15  # используемый в ботах размер «ячейки» в минутах

def init_db():
    conn = sqlite3.connect(DB_PATH)
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

    # Бронирования (Order Bot)
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

    # Блокировка спамеров
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
        state TEXT  -- 'planned' или 'active'
    )
    """)

    # Настройки рассылки
    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    # Значения по умолчанию
    cur.executemany("""
      INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)
    """, [
        ('summary_enabled', 'true'),
        ('summary_time',    '07:00'),
        ('summary_timezone','Europe/Bucharest'),
    ])

    # FAQ-entries (FAQ Bot)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS faq_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        question TEXT,
        answer TEXT,
        media_path TEXT
    )
    """)

    conn.commit()
    conn.close()


# ---------- Projects ----------
def create_project(project):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO projects(name,template_type,description,token,content)
        VALUES(?,?,?,?,?)
    """, (
        project.name,
        project.template_type,
        project.description,
        project.token,
        json.dumps(project.content)
    ))
    conn.commit()
    pid = cur.lastrowid
    conn.close()
    return pid

def get_projects(project_id=None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    if project_id:
        cur.execute("SELECT * FROM projects WHERE id=?", (project_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return {
            "id": row[0],
            "name": row[1],
            "template_type": row[2],
            "description": row[3],
            "token": row[4],
            "content": json.loads(row[5])
        }
    else:
        cur.execute("SELECT * FROM projects")
        rows = cur.fetchall()
        conn.close()
        return [
            {
              "id": r[0],
              "name": r[1],
              "template_type": r[2],
              "description": r[3],
              "token": r[4],
              "content": json.loads(r[5])
            }
            for r in rows
        ]


# ---------- Products / Services ----------
def get_products_list(project_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT id,name,short_desc,full_desc,media_path
        FROM products
        WHERE project_id=?
        ORDER BY id
    """, (project_id,))
    rows = cur.fetchall()
    conn.close()
    return [
        {"id":r[0],"name":r[1],"short_desc":r[2],"full_desc":r[3],"media":r[4] or ""}
        for r in rows
    ]

def add_product(project_id, name, short_desc, full_desc, media_path=""):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO products(project_id,name,short_desc,full_desc,media_path)
        VALUES(?,?,?,?,?)
    """, (project_id,name,short_desc,full_desc,media_path))
    conn.commit()
    pid = cur.lastrowid
    conn.close()
    return pid

def delete_product(project_id, product_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM products
        WHERE project_id=? AND id=?
    """, (project_id,product_id))
    conn.commit()
    conn.close()


# ---------- Bookings ----------
def create_booking(project_id, user_id, service_id, start_dt, duration_cells, client_name, client_phone):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO bookings(project_id,user_id,service_id,start_dt,duration_cells,client_name,client_phone)
        VALUES(?,?,?,?,?,?,?)
    """, (
        project_id,user_id,service_id,start_dt,duration_cells,client_name,client_phone
    ))
    conn.commit()
    bid = cur.lastrowid
    conn.close()
    return bid

def get_booking(booking_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT project_id,user_id,service_id,start_dt,duration_cells,client_name,client_phone,status
        FROM bookings WHERE id=?
    """, (booking_id,))
    r = cur.fetchone()
    conn.close()
    if not r:
        return None
    return {
        "project_id": r[0],
        "user_id": r[1],
        "service_id": r[2],
        "start_dt": r[3],
        "duration_cells": r[4],
        "client_name": r[5],
        "client_phone": r[6],
        "status": r[7]
    }

def update_booking_status(booking_id, status):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE bookings SET status=? WHERE id=?", (status,booking_id))
    conn.commit()
    conn.close()

def get_bookings_by_date(project_id, date_str, status="confirmed"):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT id,user_id,service_id,start_dt,duration_cells,client_name,client_phone
        FROM bookings
        WHERE project_id=? AND status=? AND substr(start_dt,1,10)=?
        ORDER BY start_dt
    """, (project_id,status,date_str))
    rows = cur.fetchall()
    conn.close()
    return [
        {
          "id":r[0],"user_id":r[1],"service_id":r[2],
          "start_dt":r[3],"duration_cells":r[4],
          "client_name":r[5],"client_phone":r[6]
        } for r in rows
    ]

def get_confirmed_future_bookings(project_id):
    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT id,start_dt,duration_cells,service_id,client_name
        FROM bookings
        WHERE project_id=? AND status='confirmed' AND start_dt>?
    """, (project_id, now))
    rows = cur.fetchall()
    conn.close()
    return [
        {"id":r[0],"start_dt":r[1],"duration_cells":r[2],"service_id":r[3],"client_name":r[4]}
        for r in rows
    ]

def get_all_bookings(project_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT id,service_id,start_dt,client_name,status
        FROM bookings
        WHERE project_id=?
    """, (project_id,))
    rows = cur.fetchall()
    conn.close()
    return [
        {"id":r[0],"service_id":r[1],"start_dt":r[2],"client_name":r[3],"status":r[4]}
        for r in rows
    ]


# ---------- Work Intervals & Exceptions ----------
def add_work_interval(project_id, start_iso, end_iso):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO work_intervals(project_id,start_dt,end_dt)
        VALUES(?,?,?)
    """, (project_id, start_iso, end_iso))
    conn.commit()
    conn.close()

def get_work_intervals(project_id, days_ahead):
    now = datetime.utcnow()
    end = now + timedelta(days=days_ahead)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT id,start_dt,end_dt
        FROM work_intervals
        WHERE project_id=? AND start_dt>=? AND start_dt<=?
        ORDER BY start_dt
    """, (project_id, now.isoformat(), end.isoformat()))
    rows = cur.fetchall()
    conn.close()
    return [{"id":r[0],"start_dt":r[1],"end_dt":r[2]} for r in rows]

def delete_work_interval(interval_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM work_intervals WHERE id=?", (interval_id,))
    conn.commit()
    conn.close()

def add_work_exception(project_id, start_iso, end_iso, state):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO work_exceptions(project_id,start_dt,end_dt,state)
        VALUES(?,?,?,?)
    """, (project_id, start_iso, end_iso, state))
    ex_id = cur.lastrowid
    conn.commit()
    conn.close()
    return ex_id

def get_planned_exceptions(project_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT id,start_dt
        FROM work_exceptions
        WHERE project_id=? AND state='planned'
    """, (project_id,))
    rows = cur.fetchall()
    conn.close()
    return [{"id":r[0],"start_dt":r[1]} for r in rows]

def activate_planned_exception(exception_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        UPDATE work_exceptions
        SET state='active'
        WHERE id=?
    """, (exception_id,))
    conn.commit()
    # вернуть интервал чтобы отменить брони
    cur.execute("SELECT start_dt,end_dt FROM work_exceptions WHERE id=?", (exception_id,))
    row = cur.fetchone()
    conn.close()
    return row  # (start_iso, end_iso)

def cancel_bookings_in_interval(project_id, start_iso, end_iso):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT id,user_id,service_id,start_dt
        FROM bookings
        WHERE project_id=? AND status='confirmed'
          AND start_dt>=? AND start_dt<=?
    """, (project_id, start_iso, end_iso))
    rows = cur.fetchall()
    cur.execute("""
        UPDATE bookings
        SET status='cancelled_by_provider'
        WHERE project_id=? AND status='confirmed'
          AND start_dt>=? AND start_dt<=?
    """, (project_id, start_iso, end_iso))
    conn.commit()
    conn.close()
    return [
        {"id":r[0],"user_id":r[1],"service_id":r[2],"start_dt":r[3]}
        for r in rows
    ]


# ---------- Settings ----------
def get_setting(key):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def set_setting(key, value):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO settings(key,value) VALUES(?,?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
    """, (key, value))
    conn.commit()
    conn.close()


# ---------- Banned Users ----------
def ban_user(project_id, user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO banned_users(project_id,user_id)
        VALUES(?,?)
    """, (project_id, user_id))
    conn.commit()
    conn.close()

def is_banned(project_id, user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT 1 FROM banned_users WHERE project_id=? AND user_id=?
    """, (project_id, user_id))
    banned = cur.fetchone() is not None
    conn.close()
    return banned


# ---------- Cart ----------
def add_to_cart(project_id, user_id, product_id, quantity=1):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT id,quantity FROM cart_items
        WHERE project_id=? AND user_id=? AND product_id=?
    """, (project_id, user_id, product_id))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE cart_items SET quantity=? WHERE id=?", (row[1]+quantity, row[0]))
    else:
        cur.execute("""
            INSERT INTO cart_items(project_id,user_id,product_id,quantity)
            VALUES(?,?,?,?)
        """, (project_id, user_id, product_id, quantity))
    conn.commit()
    conn.close()

def get_cart_items(project_id, user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT ci.id, ci.product_id, ci.quantity,
               p.name, p.full_desc, p.media_path
        FROM cart_items ci
        JOIN products p ON p.id=ci.product_id
        WHERE ci.project_id=? AND ci.user_id=?
        ORDER BY ci.id
    """, (project_id, user_id))
    rows = cur.fetchall()
    conn.close()
    return [
        {
          "cart_id":r[0],"product_id":r[1],"quantity":r[2],
          "name":r[3],"full_desc":r[4],"media":r[5] or ""
        }
        for r in rows
    ]

def update_cart_item(cart_id, new_quantity):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    if new_quantity>0:
        cur.execute("UPDATE cart_items SET quantity=? WHERE id=?", (new_quantity,cart_id))
    else:
        cur.execute("DELETE FROM cart_items WHERE id=?", (cart_id,))
    conn.commit()
    conn.close()

def delete_cart_item(cart_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM cart_items WHERE id=?", (cart_id,))
    conn.commit()
    conn.close()

def clear_cart(project_id, user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM cart_items WHERE project_id=? AND user_id=?", (project_id, user_id))
    conn.commit()
    conn.close()


# ---------- FAQ Entries ----------
def get_faq_entries(project_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT id,question,answer,media_path
        FROM faq_entries
        WHERE project_id=?
        ORDER BY id
    """, (project_id,))
    rows = cur.fetchall()
    conn.close()
    return [
        {"id":r[0],"question":r[1],"answer":r[2],"media":r[3] or ""}
        for r in rows
    ]

def add_faq_entry(project_id, question, answer, media_path=""):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO faq_entries(project_id,question,answer,media_path)
        VALUES(?,?,?,?)
    """, (project_id, question, answer, media_path))
    conn.commit()
    eid = cur.lastrowid
    conn.close()
    return eid

def delete_faq_entry(project_id, entry_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM faq_entries
        WHERE project_id=? AND id=?
    """, (project_id, entry_id))
    conn.commit()
    conn.close()
