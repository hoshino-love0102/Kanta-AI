from pydantic import BaseModel, Field


class CardCandidate(BaseModel):
    card_id: str = Field(..., description="Kanban card UUID")
    title: str
    description: str | None = None


class CommitMatchRequest(BaseModel):
    board_id: str
    commit_sha: str | None = None
    commit_message: str
    candidates: list[CardCandidate] = Field(default_factory=list)


class CommitMatchResult(BaseModel):
    card_id: str
    title: str
    score: float = Field(..., ge=0.0, le=1.0)
    reason: str


class CommitMatchResponse(BaseModel):
    matches: list[CommitMatchResult]
