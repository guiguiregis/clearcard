import os
import time
import uuid
import urllib.request
import urllib.error
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, CardApplication, FunnelEvent

API_URL = os.getenv("API_URL", "http://api:8000")
DATABASE_URL = os.environ["DATABASE_URL"]


def wait_for_api(timeout_s: int = 30) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{API_URL}/health", timeout=2) as resp:
                if resp.status == 200:
                    return
        except urllib.error.URLError:
            time.sleep(0.5)
    raise RuntimeError("API did not become healthy in time")


def main() -> None:
    wait_for_api()
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    sample_apps = [
        ("alex.mercer@example.ca", "web", "control", "ELIGIBILITY_EVALUATED"),
        ("priya.nair@example.ca", "mobile", "streamlined_offers", "OFFER_ACCEPTED"),
        ("sam.chen@example.ca", "web", "step_reorder", "KYC_PENDING"),
    ]

    with Session() as db:
        for email, surface, variant, state in sample_apps:
            existing = db.query(CardApplication).filter_by(applicant_email=email).first()
            if existing:
                continue
            app_id = uuid.uuid4()
            db.add(
                CardApplication(
                    id=app_id,
                    applicant_email=email,
                    surface=surface,
                    experiment_variant=variant,
                    state=state,
                )
            )
            db.add(
                FunnelEvent(
                    application_id=app_id,
                    event_name="step_viewed",
                    surface=surface,
                    experiment_variant=variant,
                    step_key="identity_basics",
                )
            )
        db.commit()
    print("Seed completed successfully.")


if __name__ == "__main__":
    main()
