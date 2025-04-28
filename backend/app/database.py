import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

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
    # Динамический каталог товаров/услуг
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
    # Заказы (для истории)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            user_id INTEGER,
            product TEXT,
            quantity INTEGER,
            address TEXT,
            media_path TEXT,
            status TEXT DEFAULT 'pending',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Заблокированные пользователи
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
    conn.commit()
    conn.close()

def create_project(project):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO projects (name, template_type, description, token, content)
        VALUES (?, ?, ?, ?, ?)
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

# ---------- Каталог ----------
def get_products_list(project_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, short_desc, full_desc, media_path
        FROM products
        WHERE project_id=?
        ORDER BY id
    """, (project_id,))
    rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "name": r[1], "short_desc": r[2], "full_desc": r[3], "media": r[4] or ""}
        for r in rows
    ]

def add_product(project_id, name, short_desc, full_desc, media_path):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO products (project_id, name, short_desc, full_desc, media_path)
        VALUES (?, ?, ?, ?, ?)
    """, (project_id, name, short_desc, full_desc, media_path))
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
    """, (project_id, product_id))
    conn.commit()
    conn.close()

# ---------- Заказы ----------
def save_order(data):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO orders (project_id, user_id, product, quantity, address, media_path)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        data["project_id"],
        data["user_id"],
        data["product"],
        data["quantity"],
        data["address"],
        data.get("media_path", "")
    ))
    conn.commit()
    oid = cur.lastrowid
    conn.close()
    return oid

# ---------- Блокировка ----------
def ban_user(project_id, user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO banned_users (project_id, user_id)
        VALUES (?, ?)
    """, (project_id, user_id))
    conn.commit()
    conn.close()

def is_banned(project_id, user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT 1 FROM banned_users
        WHERE project_id=? AND user_id=?
    """, (project_id, user_id))
    banned = cur.fetchone() is not None
    conn.close()
    return banned

# ---------- Корзина ----------
def add_to_cart(project_id, user_id, product_id, quantity=1):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, quantity FROM cart_items
        WHERE project_id=? AND user_id=? AND product_id=?
    """, (project_id, user_id, product_id))
    row = cur.fetchone()
    if row:
        cid, q = row
        cur.execute("UPDATE cart_items SET quantity=? WHERE id=?", (q + quantity, cid))
    else:
        cur.execute("""
            INSERT INTO cart_items (project_id, user_id, product_id, quantity)
            VALUES (?, ?, ?, ?)
        """, (project_id, user_id, product_id, quantity))
    conn.commit()
    conn.close()

def get_cart_items(project_id, user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT ci.id, ci.product_id, ci.quantity, p.name, p.full_desc, p.media_path
        FROM cart_items ci
        JOIN products p ON p.id=ci.product_id
        WHERE ci.project_id=? AND ci.user_id=?
        ORDER BY ci.id
    """, (project_id, user_id))
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "cart_id": r[0],
            "product_id": r[1],
            "quantity": r[2],
            "name": r[3],
            "full_desc": r[4],
            "media": r[5] or ""
        }
        for r in rows
    ]

def update_cart_item(cart_id, new_quantity):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    if new_quantity > 0:
        cur.execute("UPDATE cart_items SET quantity=? WHERE id=?", (new_quantity, cart_id))
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
