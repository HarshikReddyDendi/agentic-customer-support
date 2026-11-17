from sqlalchemy.orm import Session

from app.database.crud import get_order_for_customer
from app.database.models import Order


def lookup_customer_order(
    db: Session,
    *,
    order_id: int,
    customer_id: int,
) -> Order | None:
    """Return an order only when it belongs to the requesting customer."""
    return get_order_for_customer(db, order_id, customer_id)
