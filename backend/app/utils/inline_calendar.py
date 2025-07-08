from __future__ import annotations

from datetime import date, datetime
from typing import Literal
import calendar
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# ────────────────────────────────────────────────────────────────────────────
# Константы
calendar.setfirstweekday(calendar.MONDAY)

MONTH_NAMES = [
    "Январь","Февраль","Март","Апрель","Май","Июнь",
    "Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"
]
WEEK_DAYS = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]

# ────────────────────────────────────────────────────────────────────────────
# ADMIN help (зависит от booking_db)
try:
    from utils.booking_db import get_month_stats  # pylint: disable=wrong-import-position
except Exception:
    get_month_stats = None  # если модуль ещё не готов — календарь для админа не соберётся

# ────────────────────────────────────────────────────────────────────────────
# PUBLIC: create_calendar
def create_calendar(
    project_id: int,
    mode: Literal["client","view","add","del"]="client",
    year: int|None=None,
    month: int|None=None,
) -> InlineKeyboardMarkup:
    today = date.today()
    year  = year  or today.year
    month = month or today.month
    first_wd, total_days = calendar.monthrange(year, month)
    header = f"{MONTH_NAMES[month-1]} {year}"
    kb: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="〈", callback_data=_cb_prev(mode, year, month)),
         InlineKeyboardButton(text=header, callback_data="cal:ignore"),
         InlineKeyboardButton(text="〉", callback_data=_cb_next(mode, year, month))],
        [InlineKeyboardButton(text=wd, callback_data="cal:ignore") for wd in WEEK_DAYS]
    ]

    stats = get_month_stats(project_id, year, month)

    row: list[InlineKeyboardButton] = []
    for _ in range(first_wd):
        row.append(InlineKeyboardButton(text=" ", callback_data="cal:ignore"))

    for day in range(1, total_days+1):
        d  = date(year, month, day)
        ds = d.isoformat()
        s  = stats[d]

        if s.past:
            txt, cb = "—", "cal:past"
        else:
            # выбор эмодзи/префикса номера в зависимости от mode и статуса
            prefix = ""
            if mode == "client":
                if   s.total == 0:       prefix = "▫"
                elif s.booked < s.total: prefix = "🟢"
                else:                     prefix = "🔴"
            else:  # admin modes
                if mode == "view":
                    prefix = _view_emoji(s)
                elif mode == "add":
                    prefix = "🟢" if s.total == 0 else "🟠"
                else:  # del
                    if s.total == 0:
                        txt, cb = "▫", "cal:ignore"
                        row.append(InlineKeyboardButton(text=f"{txt}{day}", callback_data=cb))
                        if len(row)==7: kb.append(row); row=[]
                        continue
                    prefix = "🟠" if s.booked < s.total else "🔴"

            txt = f"{prefix}{day}"
            cb  = f"cal:{mode}:{ds}" if mode!="client" else f"cal:date:{ds}"

        row.append(InlineKeyboardButton(text=txt, callback_data=cb))
        if len(row) == 7:
            kb.append(row); row = []

    if row:
        while len(row) < 7:
            row.append(InlineKeyboardButton(text=" ", callback_data="cal:ignore"))
        kb.append(row)

    return InlineKeyboardMarkup(inline_keyboard=kb)

# ────────────────────────────────────────────────────────────────────────────
# CLIENT-only helper: обрабатываем навигацию/дату
def process_selection(call: CallbackQuery) -> tuple[bool, InlineKeyboardMarkup | date]:
    data = call.data.split(":")
    # навигация
    if data[1] in ("prev", "next"):
        yy, mm = int(data[2]), int(data[3])
        mm += -1 if data[1] == "prev" else 1
        if mm == 0:  yy -= 1; mm = 12
        if mm == 13: yy += 1; mm = 1
        return False, create_calendar(
            project_id=PROJECT_ID,
            mode="client",
            year=yy,
            month=mm
        )
    # выбор даты
    if data[1] == "date":
        sel = datetime.fromisoformat(data[2]).date()
        if sel < date.today():
            # прошлое — просто перерисовать текущий месяц
            return False, create_calendar(
                project_id=PROJECT_ID,
                mode="client"
            )
        return True, sel
    # cal:past или игнор
    return False, create_calendar(
        project_id=PROJECT_ID,
        mode="client"
    )

# ────────────────────────────────────────────────────────────────────────────
# helpers
def _cb_prev(mode: str, y: int, m: int) -> str:
    return f"cal:prev:{mode}:{y}:{m}" if mode != "client" else f"cal:prev:{y}:{m}"

def _cb_next(mode: str, y: int, m: int) -> str:
    return f"cal:next:{mode}:{y}:{m}" if mode != "client" else f"cal:next:{y}:{m}"

def _view_emoji(s) -> str:
    if s.total == 0:               return "▫"
    if s.booked == 0:              return "🟢"
    if s.booked == s.total:        return "🔴"
    return "🟠"
