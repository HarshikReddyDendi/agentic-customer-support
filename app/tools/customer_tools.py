from sqlalchemy.orm import Session

from app.database.crud import get_customer_by_email, get_customer_by_id
from app.database.models import Customer


def lookup_customer(
    db: Session,
    *,
    customer_id: int | None = None,
    email: str | None = None,
) -> Customer | None:
    if (customer_id is None) == (email is None):
        raise ValueError("Provide exactly one of customer_id or email")
    if customer_id is not None:
        return get_customer_by_id(db, customer_id)
    if email is not None:
        return get_customer_by_email(db, email.strip().lower())
    return None
