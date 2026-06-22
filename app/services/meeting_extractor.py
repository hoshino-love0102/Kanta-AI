import json
import re
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import ValidationError

from app.schemas.meeting import ActionItem, ExtractActionItemsRequest, ExtractActionItemsResponse
from app.services.openai_client import OpenAIJsonClient

_ACTION_HINTS = ("해야", "하기", "구현", "수정", "확인", "정리", "등록", "추가", "연동", "작성")
_DATE_PATTERN = re.compile(r"(20\d{2})[-./년 ]\s*(\d{1,2})[-./월 ]\s*(\d{1,2})")
_ASSIGNEE_PATTERN = re.compile(r"([가-힣A-Za-z0-9_]{2,20})\s*(?:님|가|이)?\s*(?:담당|맡|처리)")
_WEEKDAY_PATTERN = re.compile(r"(이번|다음)\s*주\s*(월|화|수|목|금|토|일)요일?")
_WEEKDAY_INDEX = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}


class MeetingExtractor:
    def __init__(self, openai_client: OpenAIJsonClient | None = None) -> None:
        self._openai_client = openai_client or OpenAIJsonClient()

    async def extract(self, request: ExtractActionItemsRequest) -> ExtractActionItemsResponse:
        if self._openai_client.enabled:
            try:
                return await self._extract_with_openai(request)
            except Exception:
                # 로컬 개발 중 API 오류가 전체 플로우를 막지 않도록 휴리스틱으로 폴백한다.
                pass
        return _extract_locally(request)

    async def _extract_with_openai(self, request: ExtractActionItemsRequest) -> ExtractActionItemsResponse:
        reference_date = _reference_date(request)
        payload = await self._openai_client.complete_json(
            system=(
                "너는 한국어 회의록에서 칸반 카드로 등록할 액션 아이템을 추출하는 서버다. "
                "반드시 JSON 객체만 반환한다. 스키마는 "
                "{summary: string, action_items: [{title: string, assignee_name: string|null, "
                "due_date: YYYY-MM-DD|null, confidence: number, evidence: string|null}]} 이다. "
                "담당자나 기한이 명시되지 않으면 추측하지 말고 null로 둔다. "
                "상대 날짜(예: 오늘, 내일, 이번 주 금요일, 다음 주 월요일)는 user payload의 "
                "current_date와 timezone을 기준으로 정확한 YYYY-MM-DD로 변환한다."
            ),
            user=json.dumps(
                {
                    "board_id": request.board_id,
                    "meeting_note_id": request.meeting_note_id,
                    "current_date": reference_date.isoformat(),
                    "timezone": request.timezone,
                    "raw_text": request.raw_text,
                },
                ensure_ascii=False,
            ),
        )
        return _parse_openai_meeting_response(payload)


def get_meeting_extractor() -> MeetingExtractor:
    return MeetingExtractor()


def _parse_openai_meeting_response(payload: dict[str, Any]) -> ExtractActionItemsResponse:
    try:
        return ExtractActionItemsResponse.model_validate(payload)
    except ValidationError:
        items = payload.get("action_items") or []
        normalized_items = []
        for item in items:
            normalized_items.append(
                {
                    "title": str(item.get("title") or "").strip(),
                    "assignee_name": item.get("assignee_name"),
                    "due_date": item.get("due_date"),
                    "confidence": float(item.get("confidence") or 0.5),
                    "evidence": item.get("evidence"),
                }
            )
        return ExtractActionItemsResponse(
            summary=str(payload.get("summary") or ""),
            action_items=[ActionItem.model_validate(item) for item in normalized_items if item["title"]],
        )


def _extract_locally(request: ExtractActionItemsRequest) -> ExtractActionItemsResponse:
    lines = [_clean_line(line) for line in request.raw_text.splitlines()]
    lines = [line for line in lines if line]

    reference_date = _reference_date(request)
    action_items = [_to_action_item(line, reference_date) for line in lines if _looks_actionable(line)]
    summary = _summarize(lines)
    return ExtractActionItemsResponse(summary=summary, action_items=action_items[:20])


def _reference_date(request: ExtractActionItemsRequest) -> date:
    if request.current_date:
        return request.current_date
    try:
        return datetime.now(ZoneInfo(request.timezone)).date()
    except ZoneInfoNotFoundError:
        return date.today()


def _clean_line(line: str) -> str:
    return line.strip(" -•\t")


def _looks_actionable(line: str) -> bool:
    return any(hint in line for hint in _ACTION_HINTS) or line.startswith(("TODO", "todo", "할일"))


def _to_action_item(line: str, reference_date: date) -> ActionItem:
    return ActionItem(
        title=_strip_prefix(line),
        assignee_name=_extract_assignee(line),
        due_date=_extract_due_date(line, reference_date),
        confidence=0.55,
        evidence=line,
    )


def _strip_prefix(line: str) -> str:
    return re.sub(r"^(TODO|todo|할일)[:：\s-]*", "", line).strip()


def _extract_assignee(line: str) -> str | None:
    match = _ASSIGNEE_PATTERN.search(line)
    return match.group(1) if match else None


def _extract_due_date(line: str, reference_date: date) -> date | None:
    absolute = _DATE_PATTERN.search(line)
    if absolute:
        year, month, day = map(int, absolute.groups())
        try:
            return date(year, month, day)
        except ValueError:
            return None

    if "오늘" in line:
        return reference_date
    if "내일" in line:
        return reference_date + timedelta(days=1)

    weekday = _WEEKDAY_PATTERN.search(line)
    if weekday:
        week_word, day_word = weekday.groups()
        target_weekday = _WEEKDAY_INDEX[day_word]
        monday = reference_date - timedelta(days=reference_date.weekday())
        if week_word == "다음":
            monday += timedelta(days=7)
        return monday + timedelta(days=target_weekday)

    return None


def _summarize(lines: list[str]) -> str:
    if not lines:
        return ""
    joined = " ".join(lines)
    return joined[:240] + ("..." if len(joined) > 240 else "")
