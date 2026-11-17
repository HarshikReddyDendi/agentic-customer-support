from sqlalchemy.orm import Session

from app.database.crud import create_support_ticket, update_support_ticket
from app.database.models import SupportTicket

__all__ = ["create_support_ticket", "update_support_ticket"]


def create_ticket(
    db: Session,
    *,
    customer_id: int,
    issue: str,
    priority: str = "Medium",
) -> SupportTicket:
    return create_support_ticket(db, customer_id, issue, priority)


def update_ticket(
    db: Session,
    ticket_id: int,
    *,
    status: str | None = None,
    priority: str | None = None,
) -> SupportTicket:
    return update_support_ticket(
        db,
        ticket_id,
        status=status,
        priority=priority,
    )
