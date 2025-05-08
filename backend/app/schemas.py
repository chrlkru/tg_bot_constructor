from pydantic import BaseModel
from typing import Dict, List, Union, Optional, Literal

# === 1) Order Bot ===
class ProductSeed(BaseModel):
    name: str
    short_descr: str
    full_descr: Optional[str] = None
    photo_file: Optional[str] = None

class OrderBotSeed(BaseModel):
    type: Literal["order_bot"]
    products: List[ProductSeed]

# === 2) FAQ Bot ===
class FAQSeed(BaseModel):
    question: str
    answer: str

class FAQBotSeed(BaseModel):
    type: Literal["faq_bot"]
    faq_items: List[FAQSeed]

# === 3) Feedback Bot (анонимные сообщения) ===
class FeedbackThreadSeed(BaseModel):
    # seed не нужен в БД, просто включаем примеры входящих сообщений
    from_user_id: int
    text: str

class FeedbackBotSeed(BaseModel):
    type: Literal["feedback_bot"]
    messages: Optional[List[FeedbackThreadSeed]] = None
    blocked:  Optional[List[int]]                 = None


# === 4) Helper Bot (alias-пасты) ===
class HelperEntrySeed(BaseModel):
    alias: str
    content: str
    photo_file: Optional[str] = None

class HelperBotSeed(BaseModel):
    type: Literal["helper_bot"]
    entries: List[HelperEntrySeed]

# === 5) Moderator Bot (белый список, настройки) ===
class ModerationSettingsSeed(BaseModel):
    allow_media: bool = False
    allow_stickers: bool = False
    censor_enabled: bool = True
    flood_max: int = 3
    flood_window_s: int = 600

class LinkWhitelistSeed(BaseModel):
    domain: str

class ModeratorBotSeed(BaseModel):
    type: Literal["moderator_bot"]
    settings: ModerationSettingsSeed
    whitelist: Optional[List[LinkWhitelistSeed]] = None

# === 6) Smart Booking CRM ===
class ServiceSeed(BaseModel):
    name: str
    duration_cells: int    # сколько ячеек занимает услуга (SLOT_SIZE_MIN)
    price: Optional[float] = None

class BookingSeed(BaseModel):
    user_id: int
    service_id: int
    start_dt: str         # ISO-строка
    duration_cells: int
    client_name: str
    client_phone: str

class SummarySettings(BaseModel):
    enabled:  bool
    time:     str  # “HH:MM”
    timezone: str

class SmartBookingSeed(BaseModel):
    type: Literal["smart_booking_crm"]
    services: List[ServiceSeed]
    work_intervals: Optional[List[Dict[str, str]]] = None
    initial_bookings: Optional[List[BookingSeed]] = None
    summary: SummarySettings  # ← вот это


# === 7) Quiz Bot (опрос) ===
class QuestionSeed(BaseModel):
    id:   int
    text: str
    options: Optional[List[str]] = None
    # можно добавить media-поле, если у вас есть фото/GIF

class QuizBotSeed(BaseModel):
    type: Literal["quiz_bot"]
    questions: List[QuestionSeed]

# И расширить ваш SeedUnion:
SeedUnion = Union[
    OrderBotSeed,
    FAQBotSeed,
    FeedbackBotSeed,
    HelperBotSeed,
    ModeratorBotSeed,
    SmartBookingSeed,
    QuizBotSeed,                # ← сюда!
]


class ProjectCreate(BaseModel):
    name: str
    template_type: str
    description: Optional[str] = None
    token: str
    content: Dict
    seed: Optional[SeedUnion] = None
