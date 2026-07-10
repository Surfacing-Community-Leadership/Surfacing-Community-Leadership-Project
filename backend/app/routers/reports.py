from fastapi import APIRouter, HTTPException

from app.models import Event, Report, User
from app.routers.deps import DB, CurrentUser
from app.schemas.report import ReportCreate, ReportRead

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("", response_model=ReportRead, status_code=201)
async def file_report(payload: ReportCreate, db: DB, user: CurrentUser):
    if payload.reported_user_id is not None:
        if await db.get(User, payload.reported_user_id) is None:
            raise HTTPException(status_code=404, detail="Reported user not found")
    if payload.reported_event_id is not None:
        if await db.get(Event, payload.reported_event_id) is None:
            raise HTTPException(status_code=404, detail="Reported event not found")

    report = Report(
        reporter_id=user.id,
        reported_user_id=payload.reported_user_id,
        reported_event_id=payload.reported_event_id,
        reason=payload.reason,
        details=payload.details,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return ReportRead(id=report.id, status=report.status)
