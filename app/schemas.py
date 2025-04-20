from pydantic import BaseModel
from typing import Dict

class BotProject(BaseModel):
    name: str
    template_type: str
    description: str
    token: str   # <-- Добавили поле token
    content: Dict
