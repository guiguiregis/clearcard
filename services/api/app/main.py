import uuid
from decimal import Decimal
from typing import Literal
from fastapi import Depends, Header, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from app.fsm import ApplicationState, assert_valid_transition
from app.idempotency import run_idempotent_endpoint
from app.models import CardApplication, FunnelEvent
from app.providers import FaultConfig, issue_virtual_card, run_kyc_and_eligibility
from app.terms import calculate_transparent_terms


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class CreateApplicationBody(BaseModel):
    applicant_email: EmailStr
    surface: Literal["web", "mobile"] = "web"
    experiment_variant: Literal["control", "streamlined_offers", "step_reorder"] = "control"


class AcceptOfferBody(BaseModel):
    selected_term_months: Literal[3, 6, 12] = 6
    preview_principal_cents: int = 120_000
    apr_percent: Decimal = Decimal("0.00")


class TermsPreviewBody(BaseModel):
    credit_limit_cents: int = 500_000
    principal_cents: int
    term_months: Literal[3, 6, 12] = 6
    apr_percent: Decimal = Decimal("0.00")


def _serialize_app(row: CardApplication, extra: dict | None = None) -> dict:
    payload = {
        "id": str(row.id),
        "applicant_email": row.applicant_email,
        "surface": row.surface,
        "experiment_variant": row.experiment_variant,
        "state": row.state,
        "version": row.version,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }
    if extra:
        payload.update(extra)
    return payload


@app.post("/terms/preview")
def preview_terms(body: TermsPreviewBody):
    try:
        breakdown = calculate_transparent_terms(
            credit_limit_cents=body.credit_limit_cents,
            principal_cents=body.principal_cents,
            term_months=body.term_months,
            apr_percent=body.apr_percent,
        )
        return breakdown.model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/applications")
def create_application(
    body: CreateApplicationBody,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    def _exec(session: Session):
        app_id = uuid.uuid4()
        row = CardApplication(
            id=app_id,
            applicant_email=str(body.applicant_email),
            surface=body.surface,
            experiment_variant=body.experiment_variant,
            state=ApplicationState.STARTED.value,
            version=1,
        )
        session.add(row)
        session.add(
            FunnelEvent(
                application_id=app_id,
                event_name="step_viewed",
                surface=body.surface,
                experiment_variant=body.experiment_variant,
                step_key="application_started",
            )
        )
        session.flush()
        return 201, _serialize_app(row)

    status_code, data, replayed = run_idempotent_endpoint(
        db,
        idempotency_key=idempotency_key,
        method="POST",
        endpoint_path="/applications",
        request_payload=body.model_dump(mode="json"),
        handler=_exec,
    )
    return JSONResponse(
        status_code=status_code,
        content=data,
        headers={"X-Idempotent-Replayed": str(replayed).lower()},
    )


@app.post("/applications/{app_id}/underwrite")
async def underwrite_application(
    app_id: uuid.UUID,
    inject_delay_ms: int = Query(default=0, ge=0, le=10000),
    inject_503: bool = Query(default=False),
    force_review: bool = Query(default=False),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    endpoint_path = f"/applications/{app_id}/underwrite"
    fault = FaultConfig(
        delay_ms=inject_delay_ms,
        fail_with_503=inject_503,
        force_manual_review=force_review,
    )

    # Lock row first so concurrent requests serialize cleanly
    locked_app = (
        db.query(CardApplication)
        .filter(CardApplication.id == app_id)
        .with_for_update()
        .first()
    )
    if not locked_app:
        raise HTTPException(status_code=404, detail="Application not found")

    provider_result = await run_kyc_and_eligibility(
        applicant_email=locked_app.applicant_email,
        fault=fault,
    )

    def _exec(session: Session):
        row = (
            session.query(CardApplication)
            .filter(CardApplication.id == app_id)
            .with_for_update()
            .first()
        )
        current = ApplicationState(row.state)

        if provider_result.get("async_pending"):
            target = ApplicationState.KYC_PENDING
        elif provider_result.get("kyc_status") == "MANUAL_REVIEW":
            target = ApplicationState.REVIEW_REQUIRED
        elif provider_result.get("eligible"):
            target = ApplicationState.ELIGIBILITY_EVALUATED
        else:
            target = ApplicationState.DECLINED

        assert_valid_transition(current, target)
        row.state = target.value
        row.version += 1
        session.add(
            FunnelEvent(
                application_id=row.id,
                event_name="fallback_triggered"
                if target in (ApplicationState.KYC_PENDING, ApplicationState.REVIEW_REQUIRED)
                else "step_completed",
                surface=row.surface,
                experiment_variant=row.experiment_variant,
                step_key="underwriting_evaluation",
            )
        )
        session.flush()
        return 200, _serialize_app(row, extra={"underwriting": provider_result})

    status_code, data, replayed = run_idempotent_endpoint(
        db,
        idempotency_key=idempotency_key,
        method="POST",
        endpoint_path=endpoint_path,
        request_payload={
            "app_id": str(app_id),
            "inject_delay_ms": inject_delay_ms,
            "inject_503": inject_503,
            "force_review": force_review,
        },
        handler=_exec,
    )
    return JSONResponse(
        status_code=status_code,
        content=data,
        headers={"X-Idempotent-Replayed": str(replayed).lower()},
    )


@app.post("/applications/{app_id}/accept-offer")
def accept_offer_and_issue_card(
    app_id: uuid.UUID,
    body: AcceptOfferBody,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    endpoint_path = f"/applications/{app_id}/accept-offer"

    def _exec(session: Session):
        row = (
            session.query(CardApplication)
            .filter(CardApplication.id == app_id)
            .with_for_update()
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="Application not found")

        assert_valid_transition(ApplicationState(row.state), ApplicationState.OFFER_ACCEPTED)
        row.state = ApplicationState.OFFER_ACCEPTED.value
        row.version += 1

        assert_valid_transition(ApplicationState(row.state), ApplicationState.CARD_PROVISIONED)
        row.state = ApplicationState.CARD_PROVISIONED.value
        row.version += 1

        card = issue_virtual_card(
            application_id=str(row.id),
            sample_principal_cents=body.preview_principal_cents,
            term_months=body.selected_term_months,
            apr_percent=body.apr_percent,
        )
        session.add(
            FunnelEvent(
                application_id=row.id,
                event_name="card_provisioned",
                surface=row.surface,
                experiment_variant=row.experiment_variant,
                step_key="offer_acceptance",
            )
        )
        session.flush()
        return 200, _serialize_app(row, extra={"virtual_card": card})

    status_code, data, replayed = run_idempotent_endpoint(
        db,
        idempotency_key=idempotency_key,
        method="POST",
        endpoint_path=endpoint_path,
        request_payload=body.model_dump(mode="json"),
        handler=_exec,
    )
    return JSONResponse(
        status_code=status_code,
        content=data,
        headers={"X-Idempotent-Replayed": str(replayed).lower()},
    )