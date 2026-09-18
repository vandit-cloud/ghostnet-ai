import uuid

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user, require_roles
from app.models.enums import Role
from app.models.user import User
from app.schemas.common import Page
from app.schemas.survey import SurveyCreate, SurveyDetailOut, SurveyOut, SurveyUpdate
from app.services import audit_service, survey_service
from app.storage.local import StorageBackend, get_storage_backend

router = APIRouter(prefix="/surveys", tags=["surveys"], dependencies=[Depends(get_current_user)])


def _to_out(db: Session, survey, detail: bool = False):
    counts = survey_service.survey_counts(db, survey.id)
    data = {
        "id": survey.id,
        "name": survey.name,
        "source": survey.source,
        "sonar_type": survey.sonar_type,
        "status": survey.status,
        "created_at": survey.created_at,
        "updated_at": survey.updated_at,
        "file_count": counts["file_count"],
        "processed_count": counts["processed_count"],
        "detection_count": counts["detection_count"],
    }
    if detail:
        data["review_count"] = counts["review_count"]
        return SurveyDetailOut(**data)
    return SurveyOut(**data)


@router.post("", response_model=SurveyOut, status_code=201)
def create_survey(
    request: Request,
    payload: SurveyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.OPERATOR)),
) -> SurveyOut:
    survey = survey_service.create_survey(db, payload, created_by_user_id=user.id)
    audit_service.log(
        db, actor=user, action="survey.created", entity_type="survey", entity_id=str(survey.id), request=request
    )
    return _to_out(db, survey)


@router.get("", response_model=Page[SurveyOut])
def list_surveys(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> Page[SurveyOut]:
    surveys, total = survey_service.list_surveys(db, page, page_size)
    return Page(items=[_to_out(db, s) for s in surveys], page=page, page_size=page_size, total=total)


@router.get("/{survey_id}", response_model=SurveyDetailOut)
def get_survey(survey_id: uuid.UUID, db: Session = Depends(get_db)) -> SurveyDetailOut:
    survey = survey_service.get_survey_or_404(db, survey_id)
    return _to_out(db, survey, detail=True)


@router.patch("/{survey_id}", response_model=SurveyDetailOut)
def update_survey(
    request: Request,
    survey_id: uuid.UUID,
    payload: SurveyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.OPERATOR)),
) -> SurveyDetailOut:
    """Rename a survey or move its status.

    Gated and audited to match `create_survey`. Router-level auth only proves
    the caller is signed in, and this endpoint can rename a survey or force its
    status, which a VIEWER or REVIEWER has no business doing -- their roles
    exist precisely to separate reading and judging from changing.
    """
    survey = survey_service.update_survey(db, survey_id, payload)
    audit_service.log(
        db, actor=user, action="survey.updated", entity_type="survey", entity_id=str(survey_id), request=request
    )
    return _to_out(db, survey, detail=True)


@router.delete("/{survey_id}", status_code=204, response_class=Response)
def delete_survey(
    request: Request,
    survey_id: uuid.UUID,
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
    user: User = Depends(require_roles(Role.ADMIN, Role.OPERATOR)),
) -> Response:
    """Erase a survey and everything derived from it. 404 if it never existed,
    so a repeated delete is honest about it rather than reporting success.

    ADMIN/OPERATOR only, and audited. This is the single most destructive call
    in the API -- it cascades to every file, frame, detection and review the
    survey owns -- and it previously carried no role check at all beyond the
    router's "is signed in", so a VIEWER could issue it. The audit entry is
    written BEFORE the delete: afterwards there is no survey row left to
    describe, and an audit trail that only records destructions it survived is
    not a trail.
    """
    survey_service.get_survey_or_404(db, survey_id)
    audit_service.log(
        db, actor=user, action="survey.deleted", entity_type="survey", entity_id=str(survey_id), request=request
    )
    survey_service.delete_survey(db, survey_id, storage)
    return Response(status_code=204)
