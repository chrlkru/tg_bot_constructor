# app/utils/inline_calendar.py

from datetime import date, timedelta
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def build_date_calendar(
    days: int,
    start_date: date | None = None,
    back_callback: str = "admin_cancel",
    row_width: int = 4
) -> InlineKeyboardMarkup:
    """
    Строит Inline-клавиатуру с кнопками выбора даты.

    :param days: число дней, начиная с `start_date` или сегодня, для показа.
    :param start_date: дата начала периода (по умолчанию today).
    :param back_callback: callback_data для кнопки «Назад».
    :param row_width: сколько кнопок в строке.
    :return: готовая InlineKeyboardMarkup.
    """
    if start_date is None:
        start_date = date.today()

    kb = InlineKeyboardMarkup(row_width=row_width)
    for i in range(days):
        d = start_date + timedelta(days=i)
        # формат: «01 янв», «02 фев» и т.д.
        text = d.strftime("%d %b")
        callback = f"date_{d.strftime('%Y%m%d')}"
        kb.insert(InlineKeyboardButton(text, callback_data=callback))

    # кнопка возврата в меню
    kb.add(InlineKeyboardButton("🔙 Главное меню", callback_data=back_callback))
    return kb
