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

# === 3) Feedback Bot ===
class FeedbackThreadSeed(BaseModel):
    from_user_id: int
    text: str

class FeedbackBotSeed(BaseModel):
    type: Literal["feedback_bot"]
    messages: Optional[List[FeedbackThreadSeed]] = None
    blocked:  Optional[List[int]]                 = None

# === 4) Helper Bot ===
class HelperEntrySeed(BaseModel):
    alias: str
    content: str
    photo_file: Optional[str] = None
    admin_only: bool = False          # ← новый флаг

class HelperBotSeed(BaseModel):
    type: Literal["helper_bot"]
    entries: List[HelperEntrySeed]

# === 5) Moderator Bot ===
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
    duration_cells: int
    price: Optional[float] = None
    category: Optional[str] = "Общее"   # ← добавить

class BookingSeed(BaseModel):
    user_id: int
    service_id: int
    start_dt: str
    duration_cells: int
    client_name: str
    client_phone: str

class SummarySettings(BaseModel):
    enabled:  bool
    time:     str
    timezone: str

class SmartBookingSeed(BaseModel):
    type: Literal["smart_booking_crm"]
    services: List[ServiceSeed]
    work_intervals: Optional[List[Dict[str, str]]] = None
    initial_bookings: Optional[List[BookingSeed]] = None
    summary: SummarySettings

# === 7) Quiz Bot ===
class QuestionSeed(BaseModel):
    id:   int
    text: str
    options: Optional[List[str]] = None

class QuizBotSeed(BaseModel):
    type: Literal["quiz_bot"]
    questions: List[QuestionSeed]

# Объединённый тип для всех сидов
SeedUnion = Union[
    OrderBotSeed,
    FAQBotSeed,
    FeedbackBotSeed,
    HelperBotSeed,
    ModeratorBotSeed,
    SmartBookingSeed,
    QuizBotSeed,
]

class ProjectCreate(BaseModel):
    name: str
    template_type: str
    description: Optional[str] = None
    token: str
    content: Dict
    seed: Optional[SeedUnion] = None
