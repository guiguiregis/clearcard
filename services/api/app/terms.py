from decimal import Decimal, ROUND_HALF_UP
from pydantic import BaseModel, Field


class InstallmentItem(BaseModel):
    installment_number: int
    principal_cents: int
    interest_cents: int
    total_cents: int
    remaining_principal_cents: int


class TermsBreakdown(BaseModel):
    credit_limit_cents: int
    principal_cents: int
    term_months: int
    apr_percent: Decimal
    total_interest_cents: int
    total_fees_cents: int = 0
    total_repayable_cents: int
    schedule: list[InstallmentItem]


def calculate_transparent_terms(
    *,
    credit_limit_cents: int = 500_000,  # $5,000.00 CAD
    principal_cents: int,
    term_months: int = 6,
    apr_percent: Decimal = Decimal("0.00"),
) -> TermsBreakdown:
    if principal_cents <= 0 or principal_cents > credit_limit_cents:
        raise ValueError("Principal must be > 0 and within approved credit limit.")
    if term_months not in (3, 6, 12):
        raise ValueError("Supported terms are 3, 6, or 12 months.")

    monthly_rate = (apr_percent / Decimal("100")) / Decimal("12")
    principal = Decimal(principal_cents)

    if monthly_rate == 0:
        base_payment = (principal / Decimal(term_months)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        schedule: list[InstallmentItem] = []
        remaining = principal_cents
        total_interest = 0

        for idx in range(1, term_months + 1):
            pay_cents = int(base_payment) if idx < term_months else remaining
            pay_cents = min(pay_cents, remaining)
            remaining -= pay_cents
            schedule.append(
                InstallmentItem(
                    installment_number=idx,
                    principal_cents=pay_cents,
                    interest_cents=0,
                    total_cents=pay_cents,
                    remaining_principal_cents=remaining,
                )
            )

        return TermsBreakdown(
            credit_limit_cents=credit_limit_cents,
            principal_cents=principal_cents,
            term_months=term_months,
            apr_percent=apr_percent,
            total_interest_cents=total_interest,
            total_fees_cents=0,
            total_repayable_cents=principal_cents + total_interest,
            schedule=schedule,
        )

    # Amortized monthly payment: P * [r(1+r)^n] / [(1+r)^n - 1]
    factor = (Decimal("1") + monthly_rate) ** term_months
    raw_payment = principal * (monthly_rate * factor) / (factor - Decimal("1"))
    target_payment_cents = int(raw_payment.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    remaining_principal = principal_cents
    total_interest_cents = 0
    schedule = []

    for idx in range(1, term_months + 1):
        interest_cents = int(
            (Decimal(remaining_principal) * monthly_rate).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
        if idx < term_months:
            principal_part = max(0, target_payment_cents - interest_cents)
            principal_part = min(principal_part, remaining_principal)
        else:
            principal_part = remaining_principal

        payment_cents = principal_part + interest_cents
        remaining_principal -= principal_part
        total_interest_cents += interest_cents

        schedule.append(
            InstallmentItem(
                installment_number=idx,
                principal_cents=principal_part,
                interest_cents=interest_cents,
                total_cents=payment_cents,
                remaining_principal_cents=remaining_principal,
            )
        )

    return TermsBreakdown(
        credit_limit_cents=credit_limit_cents,
        principal_cents=principal_cents,
        term_months=term_months,
        apr_percent=apr_percent,
        total_interest_cents=total_interest_cents,
        total_fees_cents=0,
        total_repayable_cents=principal_cents + total_interest_cents,
        schedule=schedule,
    )