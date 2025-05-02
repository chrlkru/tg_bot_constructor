# app/utils/moderation.py

import re
import time
from collections import defaultdict
from pathlib import Path

from app.utils.db_safe import transaction, safe_execute

# Путь к БД
DB_PATH = Path(__file__).resolve().parent.parent / "app" / "database.db"

# Регулярки
MAT_RE   = re.compile(r"(?:хрен|жоп|shit|fuck)", re.IGNORECASE)
URL_RE   = re.compile(r"https?://([A-Za-z0-9\.-]+)")

# Кеш для флуда: (chat_id, user_id, text) → [timestamps]
_flood_cache = defaultdict(list)

# ── Настройки ─────────────────────────────
def get_settings(project_id: int) -> dict:
    rows = safe_execute(
        "SELECT allow_media,allow_stickers,censor_enabled,flood_max,flood_window_s "
        "FROM moderation_settings WHERE project_id=?",
        (project_id,),
        DB_PATH
    )
    if rows:
        am, st, ce, fm, fw = rows[0]
        return {
            "allow_media":    bool(am),
            "allow_stickers": bool(st),
            "censor_enabled": bool(ce),
            "flood_max":      fm,
            "flood_window_s": fw
        }
    # по умолчанию
    return {
        "allow_media": False,
        "allow_stickers": False,
        "censor_enabled": True,
        "flood_max": 3,
        "flood_window_s": 600
    }

def toggle_setting(project_id: int, key: str, value: int):
    with transaction(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO moderation_settings(project_id, {}) VALUES(?,?) "
            "ON CONFLICT(project_id) DO UPDATE SET {}=excluded.{}".format(key, key, key),
            (project_id, value)
        )

# ── Белый список доменов ────────────────────
def whitelist_add(project_id: int, domain: str):
    with transaction(DB_PATH) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO link_whitelist(project_id,domain) VALUES(?,?)",
            (project_id, domain)
        )

def whitelist_del(project_id: int, domain: str):
    with transaction(DB_PATH) as conn:
        conn.execute(
            "DELETE FROM link_whitelist WHERE project_id=? AND domain=?",
            (project_id, domain)
        )

def list_whitelist(project_id: int) -> list[str]:
    rows = safe_execute(
        "SELECT domain FROM link_whitelist WHERE project_id=?",
        (project_id,),
        DB_PATH
    )
    return [r[0] for r in rows]

# ── Страйки и логи ─────────────────────────
def add_strike(project_id: int, chat_id: int, user_id: int) -> int:
    now = int(time.time())
    with transaction(DB_PATH) as conn:
        row = conn.execute(
            "SELECT strikes FROM user_warnings WHERE project_id=? AND chat_id=? AND user_id=?",
            (project_id, chat_id, user_id)
        ).fetchone()
        strikes = (row[0] if row else 0) + 1
        conn.execute(
            "INSERT INTO user_warnings(project_id,chat_id,user_id,strikes,last_ts) "
            "VALUES(?,?,?,?,?) "
            "ON CONFLICT(project_id,chat_id,user_id) DO UPDATE "
            "SET strikes=excluded.strikes, last_ts=excluded.last_ts",
            (project_id, chat_id, user_id, strikes, now)
        )
    return strikes

def log_violation(project_id: int, chat_id: int, user_id: int,
                  message_id: int, violation: str, text: str):
    ts = int(time.time())
    with transaction(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO moderation_logs(project_id,chat_id,user_id,message_id,violation,text,ts) "
            "VALUES(?,?,?,?,?,?,?)",
            (project_id, chat_id, user_id, message_id, violation, text, ts)
        )

# ── Фильтр сообщения ───────────────────────
def check_message(project_id: int, chat_id: int, user_id: int,
                  msg_text: str, content_type: str) -> list[str]:
    """
    Возвращает список кодов нарушений:
    'profanity','link','media','sticker','spam'
    """
    v = []
    settings = get_settings(project_id)

    # 1) мат
    if settings["censor_enabled"] and MAT_RE.search(msg_text):
        v.append("profanity")

    # 2) ссылки
    for dom in URL_RE.findall(msg_text):
        if dom.lower() not in [d.lower() for d in list_whitelist(project_id)]:
            v.append("link")
            break

    # 3) медиа/стикеры
    if content_type in ("photo","video","document") and not settings["allow_media"]:
        v.append("media")
    if content_type == "sticker" and not settings["allow_stickers"]:
        v.append("sticker")

    # 4) флуд
    key = (chat_id, user_id, msg_text.strip().lower())
    now = time.time()
    window = settings["flood_window_s"]
    max_rep = settings["flood_max"]
    # очистка старых
    _flood_cache[key] = [ts for ts in _flood_cache[key] if now - ts < window]
    _flood_cache[key].append(now)
    if len(_flood_cache[key]) > max_rep:
        v.append("spam")

    return list(dict.fromkeys(v))  # уникальные

# ── Форматирование /report ─────────────────
def format_report(reporter: str, orig_chat: int, orig_msg: int, reason: str) -> str:
    return (
        f"🚩 Жалоба от @{reporter} (чат {orig_chat}, msg {orig_msg})\n"
        f"Причина: {reason or '-'}"
    )
