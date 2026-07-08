from datetime import datetime
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

class Generation(Base):
    __tablename__ = "generations"

    id: Mapped[int] = mapped_column(primary_key=True)
    content_type: Mapped[str] = mapped_column(String(50))   # e.g. "enemy_bark", "item_flavor", "quest_text"
    prompt_input: Mapped[str] = mapped_column(Text)          # what the user gave us (context, character name, etc.)
    generated_output: Mapped[str] = mapped_column(Text)      # what the LLM returned
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)