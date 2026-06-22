from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.commit_matcher import _parse_openai_commit_response

client = TestClient(app)


def _disable_openai() -> None:
    get_settings.cache_clear()
    get_settings().openai_api_key = None


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_extract_action_items() -> None:
    _disable_openai()
    response = client.post(
        "/v1/meeting/action-items",
        json={
            "board_id": "board-1",
            "raw_text": "TODO: 로그인 API 구현\n민수가 2026-06-30까지 OAuth 연동 담당",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["action_items"]) >= 1


def test_extract_action_items_resolves_relative_weekday() -> None:
    _disable_openai()
    response = client.post(
        "/v1/meeting/action-items",
        json={
            "board_id": "board-1",
            "current_date": "2026-06-22",
            "timezone": "Asia/Seoul",
            "raw_text": "로그인 API를 이번 주 금요일까지 구현하기",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["action_items"][0]["due_date"] == "2026-06-26"


def test_match_commit() -> None:
    _disable_openai()
    response = client.post(
        "/v1/commit/match",
        json={
            "board_id": "board-1",
            "commit_sha": "abc123",
            "commit_message": "feat: 로그인 API 구현",
            "candidates": [
                {"card_id": "card-1", "title": "로그인 API 구현"},
                {"card_id": "card-2", "title": "회의록 요약 UI 수정"},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["matches"][0]["card_id"] == "card-1"


def test_parse_openai_commit_response_filters_low_scores() -> None:
    response = _parse_openai_commit_response(
        {
            "matches": [
                {
                    "card_id": "card-1",
                    "title": "로그인 API 구현",
                    "score": 0.95,
                    "reason": "명확히 일치함",
                },
                {
                    "card_id": "card-2",
                    "title": "회의록 요약 UI 수정",
                    "score": 0.0,
                    "reason": "관련성이 없음",
                },
            ]
        }
    )

    assert [match.card_id for match in response.matches] == ["card-1"]
