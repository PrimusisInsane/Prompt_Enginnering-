from pydantic import BaseModel

class BarkResponse(BaseModel):
    content_type: str
    enemy_type: str
    lines: list[str]