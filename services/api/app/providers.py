import asyncio
import random
import uuid
from dataclasses import dataclass
from decimal import Decimal
from fastapi import HTTPException
from app.terms import TermsBreakdown, calculate_transparent_terms


@dataclass
class FaultConfig:
    delay_ms: int = 0
    fail_with_503: bool = False
    force_manual_review: bool = False
    sync_timeout_ms: int = 2500


class TransientProviderError(Exception):
    pass


async def _simulate_call(name: str, fault: FaultConfig, operation) -> dict:
    if fault.delay_ms > 0:
        await asyncio.sleep(fault.delay_ms / 1000.0)

    if fault.fail_with_503:
        raise TransientProviderError(f"{name} returned simulated HTTP 503")

    if fault.delay_ms > fault.sync_timeout_ms:
        return {"async_pending": True, "provider": name}

    return operation()


async def run_kyc_and_eligibility(
    *,
    applicant_email: str,
    fault: FaultConfig,
    max_retries: int = 2,
) -> dict:
    attempt = 0
    while True:
        try:
            return await _simulate_call(
                "kyc_and_bureau",
                fault,
                lambda: {
                    "kyc_status": "MANUAL_REVIEW" if fault.force_manual_review else "VERIFIED",
                    "eligible": not fault.force_manual_review,
                    "credit_limit_cents": 500_000,
                    "apr_percent": "0.00" if applicant_email.endswith(".ca") else "9.99",
                    "decision_id": f"dec_{uuid.uuid4().hex[:12]}",
                },
            )
        except TransientProviderError as exc:
            if attempt >= max_retries:
                raise HTTPException(
                    status_code=503,
                    detail=f"Underwriting provider unavailable after {max_retries + 1} attempts: {exc}",
                )
            backoff_s = (0.05 * (2**attempt)) + random.uniform(0, 0.03)
            await asyncio.sleep(backoff_s)
            attempt += 1


def issue_virtual_card(
    *,
    application_id: str,
    sample_principal_cents: int = 120_000,
    term_months: int = 6,
    apr_percent: Decimal = Decimal("0.00"),
) -> dict:
    terms: TermsBreakdown = calculate_transparent_terms(
        principal_cents=sample_principal_cents,
        term_months=term_months,
        apr_percent=apr_percent,
    )
    suffix = uuid.uuid4().hex[:4].upper()
    return {
        "card_token": f"tok_card_{uuid.uuid4().hex[:16]}",
        "masked_pan": f"4532 •••• •••• {suffix}",
        "status": "ACTIVE",
        "application_id": application_id,
        "sample_terms": terms.model_dump(mode="json"),
    }