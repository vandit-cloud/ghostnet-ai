import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import ApiError
from app.models.enums import ReportFormat, ReportStatus
from app.schemas.report import ReportCreate, ReportOut
from app.services import report_service
from app.storage.local import StorageBackend, get_storage_backend

router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(get_current_user)])


@router.post("", response_model=ReportOut, status_code=202)
async def create_report(payload: ReportCreate, db: Session = Depends(get_db)) -> ReportOut:
    report = report_service.create_report(db, payload)
    return ReportOut.model_validate(report)


@router.get("", response_model=list[ReportOut])
def list_reports(survey_id: uuid.UUID | None = None, db: Session = Depends(get_db)) -> list[ReportOut]:
    reports = report_service.list_reports(db, survey_id)
    return [ReportOut.model_validate(r) for r in reports]


@router.get("/{report_id}", response_model=ReportOut)
def get_report(report_id: uuid.UUID, db: Session = Depends(get_db)) -> ReportOut:
    report = report_service.get_report_or_404(db, report_id)
    return ReportOut.model_validate(report)


@router.get("/{report_id}/download")
def download_report(
    report_id: uuid.UUID,
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
) -> StreamingResponse:
    report = report_service.get_report_or_404(db, report_id)
    if report.status != ReportStatus.COMPLETED or not report.storage_reference:
        raise ApiError(409, "REPORT_NOT_READY", "Report has not finished generating.")

    media_type = "text/csv" if report.format == ReportFormat.CSV else "application/json"
    ext = "csv" if report.format == ReportFormat.CSV else "json"
    stream = storage.open(report.storage_reference)
    return StreamingResponse(
        stream,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="report-{report.id}.{ext}"'},
    )
