import sqlite3
from contextlib import contextmanager
from pathlib import Path

# Путь к файлу базы данных
DB_PATH = Path(__file__).parent / "order_bot.db"

@contextmanager
def _conn():
    """Контекстный менеджер для подключения к SQLite с автоматическим commit/rollback."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """Создаёт таблицы базы данных (если не существуют) и добавляет тестовые данные при первом запуске."""
    with _conn() as db:
        # Таблица товаров
        db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                name       TEXT,
                short_desc TEXT,
                full_desc  TEXT,
                media_path TEXT
            )
        """)
        # Таблица элементов корзины
        db.execute("""
            CREATE TABLE IF NOT EXISTS cart_items (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                user_id    INTEGER,
                product_id INTEGER,
                quantity   INTEGER DEFAULT 1
            )
        """)
        # Таблица заказов
        db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                user_id    INTEGER,
                product    INTEGER,
                quantity   INTEGER,
                address    TEXT,
                media_path TEXT
            )
        """)
        # Таблица заблокированных пользователей (черный список)
        db.execute("""
            CREATE TABLE IF NOT EXISTS banned_users (
                project_id INTEGER,
                user_id    INTEGER,
                PRIMARY KEY(project_id, user_id)
            )
        """)
        # Добавление тестовых товаров при первом запуске (если таблица пуста)
        cur = db.execute("SELECT COUNT(*) AS count FROM products WHERE project_id=?", (3,))
        count = cur.fetchone()["count"]
        if count == 0:
            # Предполагается, что файл изображения указанного имени присутствует в media/3/
            db.execute(
                "INSERT INTO products(project_id, name, short_desc, full_desc, media_path) VALUES (?, ?, ?, ?, ?)",
                (3, "Тестовый товар 1", "Краткое описание товара 1, цена 100 ₽", "Полное описание товара 1", "64e7f702-5af9-458c-a093-de0939c808a0.png")
            )
            db.execute(
                "INSERT INTO products(project_id, name, short_desc, full_desc, media_path) VALUES (?, ?, ?, ?, ?)",
                (3, "Тестовый товар 2", "Краткое описание товара 2, цена 200 ₽", "Полное описание товара 2", "64e7f702-5af9-458c-a093-de0939c808a0.png")
            )

def get_products_list(project_id: int) -> list[dict]:
    """Возвращает список всех товаров (в виде списка словарей)."""
    with _conn() as db:
        cur = db.execute(
            "SELECT id, name, short_desc, full_desc, media_path FROM products WHERE project_id=? ORDER BY id",
            (project_id,)
        )
        return [
            {
                "id": r["id"], "name": r["name"],
                "short_desc": r["short_desc"], "full_desc": r["full_desc"],
                "media": r["media_path"] or ""
            }
            for r in cur.fetchall()
        ]

def add_product(project_id: int, name: str, short_desc: str, full_desc: str, media_path: str = "") -> int:
    """Добавляет новый товар в таблицу products. Возвращает его id."""
    with _conn() as db:
        cur = db.execute(
            "INSERT INTO products(project_id, name, short_desc, full_desc, media_path) VALUES (?, ?, ?, ?, ?)",
            (project_id, name, short_desc, full_desc, media_path)
        )
        return cur.lastrowid

def delete_product(project_id: int, product_id: int):
    """Удаляет товар из таблицы products по id (в рамках указанного проекта)."""
    with _conn() as db:
        db.execute("DELETE FROM products WHERE project_id=? AND id=?", (project_id, product_id))

def add_to_cart(project_id: int, user_id: int, product_id: int, quantity: int = 1):
    """Добавляет товар в корзину пользователя. Если товар уже есть, увеличивает количество."""
    with _conn() as db:
        row = db.execute(
            "SELECT id, quantity FROM cart_items WHERE project_id=? AND user_id=? AND product_id=?",
            (project_id, user_id, product_id)
        ).fetchone()
        if row:
            # Товар уже в корзине – обновляем количество
            new_qty = row["quantity"] + quantity
            db.execute("UPDATE cart_items SET quantity=? WHERE id=?", (new_qty, row["id"]))
        else:
            # Добавляем новую позицию в корзину
            db.execute(
                "INSERT INTO cart_items(project_id, user_id, product_id, quantity) VALUES (?, ?, ?, ?)",
                (project_id, user_id, product_id, quantity)
            )

def get_cart_items(project_id: int, user_id: int) -> list[dict]:
    """Возвращает содержимое корзины пользователя (список словарей с данными по каждому товару)."""
    with _conn() as db:
        cur = db.execute(
            "SELECT ci.id AS cart_id, ci.product_id, ci.quantity, p.name, p.full_desc, p.media_path "
            "FROM cart_items ci JOIN products p ON p.id = ci.product_id "
            "WHERE ci.project_id=? AND ci.user_id=? ORDER BY ci.id",
            (project_id, user_id)
        )
        return [
            {
                "cart_id": r["cart_id"], "product_id": r["product_id"],
                "quantity": r["quantity"],
                "name": r["name"], "full_desc": r["full_desc"],
                "media": r["media_path"] or ""
            }
            for r in cur.fetchall()
        ]

def update_cart_item(cart_id: int, new_qty: int):
    """Обновляет количество товара в корзине (или удаляет, если количество стало 0)."""
    with _conn() as db:
        if new_qty > 0:
            db.execute("UPDATE cart_items SET quantity=? WHERE id=?", (new_qty, cart_id))
        else:
            db.execute("DELETE FROM cart_items WHERE id=?", (cart_id,))

def delete_cart_item(cart_id: int):
    """Удаляет позицию из корзины по её идентификатору."""
    with _conn() as db:
        db.execute("DELETE FROM cart_items WHERE id=?", (cart_id,))

def clear_cart(project_id: int, user_id: int):
    """Очищает корзину пользователя (удаляет все позиции)."""
    with _conn() as db:
        db.execute("DELETE FROM cart_items WHERE project_id=? AND user_id=?", (project_id, user_id))

def save_order(order: dict):
    """Сохраняет один товар из заказа в таблицу orders."""
    with _conn() as db:
        db.execute(
            "INSERT INTO orders(project_id, user_id, product, quantity, address, media_path) VALUES (?, ?, ?, ?, ?, ?)",
            (order["project_id"], order["user_id"], order["product"], order["quantity"], order.get("address", ""), order.get("media_path", ""))
        )

def is_banned(project_id: int, user_id: int) -> bool:
    """Проверяет, заблокирован ли пользователь (находится ли в списке banned_users)."""
    with _conn() as db:
        res = db.execute("SELECT 1 FROM banned_users WHERE project_id=? AND user_id=?", (project_id, user_id)).fetchone()
        return bool(res)
def ban_user(project_id: int, user_id: int):
    """Добавить пользователя в чёрный список."""
    with _conn() as db:
        db.execute(
            "INSERT OR IGNORE INTO banned_users(project_id,user_id) VALUES(?,?)",
            (project_id, user_id)
        )

def unban_user(project_id: int, user_id: int):
    """Убрать пользователя из чёрного списка."""
    with _conn() as db:
        db.execute(
            "DELETE FROM banned_users WHERE project_id=? AND user_id=?",
            (project_id, user_id)
        )
