"""
app/seeders.py
--------------
Засев стартовых данных в базу для всех шаблонов ботов
(вызывается единожды после POST /projects).
"""

import json
import logging
import pdb
from datetime import datetime, timedelta
from typing import Any

from app.utils import booking_db
from app.utils.media import save_media_file, MEDIA_ROOT
from app.utils.order_db import add_product
# --- Pydantic-модели сидов --------------------------------------------
from app.schemas import (
    SeedUnion,
    OrderBotSeed,
    FAQBotSeed,
    HelperBotSeed,
    FeedbackBotSeed,
    ModeratorBotSeed,
    SmartBookingSeed,
    QuizBotSeed,
)

# --- CRUD-функции из app.database --------------------------------------
from app.database import (
    get_projects,
    update_project_content,
    add_product,
    add_faq_entry,
    create_booking,
    set_setting,
    add_product  # для услуг Smart-Booking
)

# --- Утилиты ------------------------------------------------------------
from app.utils.helper_db import add_helper_entry
from app.utils.feedback import log_feedback, block_user as fb_block_user
from app.utils.moderation import toggle_setting as mod_toggle_setting, whitelist_add
from app.schemas import SmartBookingSeed
from app.database import (
    crm_add_service         as bk_add_service,
    crm_add_slot            as bk_add_interval,
    crm_create_booking_safe as bk_create_booking,
    crm_set_project_setting as bk_set_setting,
    crm_safe_execute as bk_safe_execute, # ← уже определена
)

# 1) Order-bot: товары ---------------------------------------------------
def seed_order_bot(pid: int, seed: OrderBotSeed) -> None:
    for item in seed.products:
        add_product(
            pid,
            item.name,
            item.short_descr,
            item.full_descr,
            item.photo_file or ""   # уже оригинальное имя
        )



# 2) FAQ-bot: вопросы-ответы ---------------------------------------------
def seed_faq_bot(pid: int, seed: FAQBotSeed) -> None:
    for qa in seed.faq_items:
        add_faq_entry(pid, qa.question, qa.answer, "")


# 3) Helper-bot: alias-пасты ---------------------------------------------
def seed_helper_bot(pid: int, seed: HelperBotSeed) -> None:
    for entry in seed.entries:
        add_helper_entry(pid,
                         entry.alias,
                         entry.content,
                         entry.photo_file or "")


# 4) Feedback-bot: треды и блок-лист ------------------------------------
def seed_feedback_bot(pid: int, seed: FeedbackBotSeed) -> None:
    # предполагаем, что все сообщения — входящие
    if seed.messages:
        for msg in seed.messages:
            log_feedback(pid,
                         msg.from_user_id,  # <- правильно
                         "in",              # жёстко «in», или расширить схему
                         msg.text)
    if seed.blocked:
        for uid in seed.blocked:
            fb_block_user(pid, uid)


# 5) Moderator-bot: настройки и whitelist -------------------------------
def seed_moderator_bot(pid: int, seed: ModeratorBotSeed) -> None:
    s = seed.settings
    mod_toggle_setting(pid, "allow_media",     int(s.allow_media))
    mod_toggle_setting(pid, "allow_stickers",   int(s.allow_stickers))
    mod_toggle_setting(pid, "censor_enabled",   int(s.censor_enabled))
    mod_toggle_setting(pid, "flood_max",        s.flood_max)
    mod_toggle_setting(pid, "flood_window_s",   s.flood_window_s)

    if seed.whitelist:
        for w in seed.whitelist:
            whitelist_add(pid, w.domain)


# 6) Smart-Booking CRM: услуги, интервалы, брони, сводка ------------------
def seed_smart_booking(pid: int, seed: SmartBookingSeed) -> None:
    # 1️⃣ Засеваем услуги
    for svc in seed.services:
        # категория приходит из JSON либоа используем "Общее"
        category = svc.category or "Общее"
        bk_add_service(
            pid,
            svc.name,
            str(svc.price or 0),     # price хранится как TEXT
            svc.duration_cells,      # число 15-минутных ячеек
            category
        )

    # 2️⃣ Засеваем интервалы: разбиваем каждый интервал на 15-минутки
    for iv in seed.work_intervals or []:
        dt_start = datetime.fromisoformat(iv["start"])
        dt_end   = datetime.fromisoformat(iv["end"])
        cur = dt_start
        while cur < dt_end:
            date_str = cur.date().isoformat()
            time_str = cur.strftime("%H:%M")
            bk_add_interval(pid, date_str, time_str)
            cur += timedelta(minutes=15)

    # 3️⃣ Засеваем начальные брони
    for b in seed.initial_bookings or []:
        dt = datetime.fromisoformat(b.start_dt)
        date_str = dt.date().isoformat()
        time_str = dt.strftime("%H:%M")

        # найдём slot_id по дате и времени
        rows = bk_safe_execute(
            "SELECT id FROM work_intervals WHERE project_id=? AND date=? AND time=?",
            (pid, date_str, time_str)
        )
        if not rows:
            logging.warning("Seed: слот %s %s не найден – пропускаем", date_str, time_str)
            continue

        slot_id = rows[0]["id"]
        res = bk_create_booking(
            pid,
            b.user_id,
            b.service_id,
            slot_id,
            details=f"{b.client_name}; {b.client_phone}"
        )
        if res is None:
            logging.warning(
                "Seed: не удалось забронировать слот %d для пользователя %d",
                slot_id, b.user_id
            )

    # 4️⃣ Засеваем настройки сводки
    s = seed.summary
    bk_set_setting(pid, "summary_enabled",  "true" if s.enabled else "false")
    bk_set_setting(pid, "summary_time",     s.time)
    bk_set_setting(pid, "summary_timezone", s.timezone)


# 7) Quiz-bot: просто кладём вопросы в content ---------------------------
def seed_quiz_bot(pid: int, seed: QuizBotSeed) -> None:
    proj = get_projects(pid)
    content = proj["content"] or {}
    content["questions"] = [q.dict() for q in seed.questions]
    update_project_content(pid, content)


# Универсальная точка входа ---------------------------------------------
def apply_seed(project_id: int, seed: SeedUnion) -> None:
    t = seed.type
    if t == "order_bot":
        seed_order_bot(project_id, seed)
    elif t == "faq_bot":
        seed_faq_bot(project_id, seed)
    elif t == "helper_bot":
        seed_helper_bot(project_id, seed)
    elif t == "feedback_bot":
        seed_feedback_bot(project_id, seed)
    elif t == "moderator_bot":
        seed_moderator_bot(project_id, seed)
    elif t == "smart_booking_crm":
        seed_smart_booking(project_id, seed)
    elif t == "quiz_bot":
        seed_quiz_bot(project_id, seed)
    else:
        raise ValueError(f"Неизвестный тип сидов: {t}")
