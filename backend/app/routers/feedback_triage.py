from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from human_feedback.decision_policy import FeedbackTriageInput, TriageFeedback

from ..dependencies import get_feedback_triage

router = APIRouter(prefix="/api/v2/feedback", tags=["feedback-triage"])


class FeedbackTriageRequest(BaseModel):
    site_id: str = Field(min_length=1, max_length=100)
    comment: str = Field(min_length=1, max_length=4000)

    @field_validator("site_id", "comment")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class FeedbackTriageResponse(BaseModel):
    category: Literal[
        "data_quality",
        "model_behavior",
        "agronomic_context",
        "usability",
        "other",
        "unclassified",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    provider: str
    model_revision: str | None
    abstained: bool
    reason: str | None
    human_review_required: Literal[True]


@router.post("/triage", response_model=FeedbackTriageResponse)
def triage_feedback(
    body: FeedbackTriageRequest,
    triage: TriageFeedback = Depends(get_feedback_triage),
) -> FeedbackTriageResponse:
    result = triage.execute(FeedbackTriageInput(site_id=body.site_id, comment=body.comment))
    return FeedbackTriageResponse(
        category=result.category,
        confidence=result.confidence,
        provider=result.provider,
        model_revision=result.model_revision,
        abstained=result.abstained,
        reason=result.reason,
        human_review_required=True,
    )
