"""Plan publishes a Day Plan ZIP (Issue #917). Combined image only."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

from app.core.execute.published_plan import PublishedPlanError
from app.utils.auth import is_session_valid
from app.utils.env import env_bool

router = APIRouter()


class PublishBody(BaseModel):
    run_id: str
    day: str
    calendar_date: str
    name: Optional[str] = None
    event_series: Optional[str] = None
    event_edition: Optional[str] = None


def _guard(request: Request) -> None:
    if env_bool("CLOUD_MODE") and not is_session_valid(request):
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/api/plan/plans")
async def publish_plan(request: Request, body: PublishBody):
    _guard(request)
    from app.core.plan.publish_day_plan import publish_day_plan_zip

    try:
        archive = publish_day_plan_zip(
            run_id=body.run_id.strip(),
            day=body.day.strip().lower(),
            calendar_date=body.calendar_date.strip(),
            name=body.name,
            event_series=body.event_series,
            event_edition=body.event_edition,
        )
    except PublishedPlanError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    filename = f"day-plan-{body.calendar_date}.zip"
    disposition = f'attachment; filename="{filename}"'
    return Response(
        content=archive,
        media_type="application/zip",
        headers={"Content-Disposition": disposition},
    )
