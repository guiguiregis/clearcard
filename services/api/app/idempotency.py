import hashlib
import json
from typing import Any, Callable
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models import IdempotencyRecord


def compute_request_hash(method: str, path: str, body: Any) -> str:
    canonical = json.dumps(
        {"method": method.upper(), "path": path, "body": body},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def run_idempotent_endpoint(
    db: Session,
    *,
    idempotency_key: str | None,
    method: str,
    endpoint_path: str,
    request_payload: dict[str, Any],
    handler: Callable[[Session], tuple[int, dict[str, Any]]],
) -> tuple[int, dict[str, Any], bool]:
    """
    Executes `handler` once per `(idempotency_key, endpoint_path)`.
    Returns `(status_code, response_body, replayed)`.
    """
    if not idempotency_key or len(idempotency_key.strip()) < 8:
        raise HTTPException(
            status_code=400,
            detail="Missing or invalid Idempotency-Key header (must be at least 8 characters).",
        )

    key = idempotency_key.strip()
    req_hash = compute_request_hash(method, endpoint_path, request_payload)

    existing = (
        db.query(IdempotencyRecord)
        .filter_by(idempotency_key=key, endpoint_path=endpoint_path)
        .first()
    )
    if existing:
        if existing.request_hash != req_hash:
            raise HTTPException(
                status_code=422,
                detail="Idempotency-Key reuse detected with a different request payload.",
            )
        return existing.response_status, existing.response_body, True

    status_code, body = handler(db)

    record = IdempotencyRecord(
        idempotency_key=key,
        endpoint_path=endpoint_path,
        request_hash=req_hash,
        response_status=status_code,
        response_body=body,
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        race_winner = (
            db.query(IdempotencyRecord)
            .filter_by(idempotency_key=key, endpoint_path=endpoint_path)
            .first()
        )
        if race_winner and race_winner.request_hash == req_hash:
            return race_winner.response_status, race_winner.response_body, True
        raise

    return status_code, body, False