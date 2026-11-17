from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Customer, Order, SupportTicket


def get_customer_by_id(db: Session, customer_id: int) -> Customer | None:
    return db.scalar(select(Customer).where(Customer.id == customer_id))


def get_customer_by_email(db: Session, email: str) -> Customer | None:
    return db.scalar(select(Customer).where(Customer.email == email))


def get_order_for_customer(
    db: Session,
    order_id: int,
    customer_id: int,
) -> Order | None:
    return db.scalar(
        select(Order).where(
            Order.id == order_id,
            Order.customer_id == customer_id,
        )
    )


def create_support_ticket(
    db: Session,
    customer_id: int,
    issue: str,
    priority: str = "Medium",
) -> SupportTicket:
    if get_customer_by_id(db, customer_id) is None:
        raise LookupError(f"Customer {customer_id} was not found")
    if not issue.strip():
        raise ValueError("Ticket issue cannot be empty")
    if priority not in {"Low", "Medium", "High"}:
        raise ValueError("Ticket priority must be Low, Medium, or High")

    ticket = SupportTicket(
        customer_id=customer_id,
        issue=issue.strip(),
        priority=priority,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def update_support_ticket(
    db: Session,
    ticket_id: int,
    *,
    status: str | None = None,
    priority: str | None = None,
) -> SupportTicket:
    ticket = db.get(SupportTicket, ticket_id)
    if ticket is None:
        raise LookupError(f"Support ticket {ticket_id} was not found")
    if status is None and priority is None:
        raise ValueError("At least one ticket field must be provided")
    if status is not None:
        if not status.strip():
            raise ValueError("Ticket status cannot be empty")
        if status not in {"Open", "In Progress", "Resolved", "Closed"}:
            raise ValueError(
                "Ticket status must be Open, In Progress, Resolved, or Closed"
            )
        ticket.status = status.strip()
    if priority is not None:
        if not priority.strip():
            raise ValueError("Ticket priority cannot be empty")
        if priority not in {"Low", "Medium", "High"}:
            raise ValueError("Ticket priority must be Low, Medium, or High")
        ticket.priority = priority.strip()

    db.commit()
    db.refresh(ticket)
    return ticket
