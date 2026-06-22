import json
import re
from difflib import SequenceMatcher
from typing import Any

from app.schemas.commit import CommitMatchRequest, CommitMatchResponse, CommitMatchResult
from app.services.openai_client import OpenAIJsonClient

_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9가-힣]+")
MIN_MATCH_SCORE = 0.35


class CommitMatcher:
    def __init__(self, openai_client: OpenAIJsonClient | None = None) -> None:
        self._openai_client = openai_client or OpenAIJsonClient()

    async def match(self, request: CommitMatchRequest) -> CommitMatchResponse:
        if self._openai_client.enabled and request.candidates:
            try:
                return await self._match_with_openai(request)
            except Exception:
                pass
        return _match_locally(request)

    async def _match_with_openai(self, request: CommitMatchRequest) -> CommitMatchResponse:
        payload = await self._openai_client.complete_json(
            system=(
                "너는 Git commit 메시지와 칸반 카드 후보를 매칭하는 서버다. "
                "반드시 JSON 객체만 반환한다. 스키마는 "
                "{matches: [{card_id: string, title: string, score: number, reason: string}]} 이다. "
                "score는 0~1 사이이며, score가 0.35 미만인 후보나 관련 없는 후보는 절대 "
                "matches에 포함하지 않는다. 최대 3개만 반환한다."
            ),
            user=json.dumps(request.model_dump(), ensure_ascii=False),
        )
        return _parse_openai_commit_response(payload)


def get_commit_matcher() -> CommitMatcher:
    return CommitMatcher()


def _parse_openai_commit_response(payload: dict[str, Any]) -> CommitMatchResponse:
    matches = payload.get("matches") or []
    results = []
    for item in matches[:3]:
        try:
            results.append(
                CommitMatchResult(
                    card_id=str(item.get("card_id") or ""),
                    title=str(item.get("title") or ""),
                    score=max(0.0, min(1.0, float(item.get("score") or 0.0))),
                    reason=str(item.get("reason") or "AI 유사도 판단"),
                )
            )
        except Exception:
            continue
    results = [
        item
        for item in results
        if item.card_id and item.title and item.score >= MIN_MATCH_SCORE
    ]
    results.sort(key=lambda item: item.score, reverse=True)
    return CommitMatchResponse(matches=results)


def _match_locally(request: CommitMatchRequest) -> CommitMatchResponse:
    message = _normalize(request.commit_message)
    results: list[CommitMatchResult] = []

    for candidate in request.candidates:
        target = _normalize(f"{candidate.title} {candidate.description or ''}")
        score = _similarity(message, target)
        if score >= MIN_MATCH_SCORE:
            results.append(
                CommitMatchResult(
                    card_id=candidate.card_id,
                    title=candidate.title,
                    score=round(score, 4),
                    reason="커밋 메시지와 카드 제목/설명 텍스트가 유사합니다.",
                )
            )

    results.sort(key=lambda item: item.score, reverse=True)
    return CommitMatchResponse(matches=results[:3])


def _normalize(text: str) -> str:
    return " ".join(_TOKEN_PATTERN.findall(text.lower()))


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0

    left_tokens = set(left.split())
    right_tokens = set(right.split())
    jaccard = len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)
    sequence = SequenceMatcher(None, left, right).ratio()
    return (jaccard * 0.65) + (sequence * 0.35)
