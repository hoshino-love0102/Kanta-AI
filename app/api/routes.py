from fastapi import APIRouter, Depends

from app.schemas.commit import CommitMatchRequest, CommitMatchResponse
from app.schemas.meeting import ExtractActionItemsRequest, ExtractActionItemsResponse
from app.services.commit_matcher import CommitMatcher, get_commit_matcher
from app.services.meeting_extractor import MeetingExtractor, get_meeting_extractor

router = APIRouter()


@router.post("/meeting/action-items", response_model=ExtractActionItemsResponse)
async def extract_action_items(
    request: ExtractActionItemsRequest,
    extractor: MeetingExtractor = Depends(get_meeting_extractor),
) -> ExtractActionItemsResponse:
    return await extractor.extract(request)


@router.post("/commit/match", response_model=CommitMatchResponse)
async def match_commit(
    request: CommitMatchRequest,
    matcher: CommitMatcher = Depends(get_commit_matcher),
) -> CommitMatchResponse:
    return await matcher.match(request)
