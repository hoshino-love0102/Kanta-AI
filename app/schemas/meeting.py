from datetime import date

from pydantic import BaseModel, Field


class ExtractActionItemsRequest(BaseModel):
    meeting_note_id: str | None = None
    board_id: str
    raw_text: str = Field(..., min_length=1)
    current_date: date | None = Field(
        default=None,
        description="상대 날짜 해석 기준일. 예: 2026-06-22",
    )
    timezone: str = Field(default="Asia/Seoul")


class ActionItem(BaseModel):
    title: str
    assignee_name: str | None = None
    due_date: date | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: str | None = None


class ExtractActionItemsResponse(BaseModel):
    summary: str
    action_items: list[ActionItem]
