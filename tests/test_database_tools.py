import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.connection import Base
from app.database.models import Customer, Order
from app.database.crud import (
    create_support_ticket,
    get_order_for_customer,
    update_support_ticket,
)
from app.tools.customer_tools import lookup_customer


class DatabaseToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        customer = Customer(name="Test Customer", email="test@example.com")
        self.session.add(customer)
        self.session.commit()
        self.session.refresh(customer)
        self.customer_id = customer.id
        order = Order(
            customer_id=customer.id,
            product="Test Item",
            amount=12.50,
            status="Processing",
        )
        self.session.add(order)
        self.session.commit()
        self.session.refresh(order)
        self.order_id = order.id

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_order_lookup_checks_customer_ownership(self) -> None:
        owned_order = get_order_for_customer(
            self.session,
            self.order_id,
            self.customer_id,
        )
        other_customer_order = get_order_for_customer(
            self.session,
            self.order_id,
            self.customer_id + 1,
        )

        self.assertIsNotNone(owned_order)
        self.assertIsNone(other_customer_order)

    def test_customer_lookup_by_email_is_case_insensitive(self) -> None:
        customer = lookup_customer(
            self.session,
            email="TEST@example.com",
        )

        self.assertIsNotNone(customer)
        self.assertEqual(customer.id, self.customer_id)

    def test_ticket_creation_and_update(self) -> None:
        ticket = create_support_ticket(
            self.session,
            self.customer_id,
            "Package arrived damaged",
            "High",
        )
        updated = update_support_ticket(
            self.session,
            ticket.id,
            status="In Progress",
        )

        self.assertEqual(updated.status, "In Progress")
        self.assertEqual(updated.priority, "High")

    def test_ticket_creation_rejects_unknown_customer(self) -> None:
        with self.assertRaisesRegex(LookupError, "was not found"):
            create_support_ticket(
                self.session,
                self.customer_id + 1,
                "Issue",
            )

    def test_ticket_update_requires_a_change(self) -> None:
        ticket = create_support_ticket(
            self.session,
            self.customer_id,
            "Issue",
        )
        with self.assertRaisesRegex(ValueError, "At least one"):
            update_support_ticket(self.session, ticket.id)

    def test_ticket_rejects_invalid_status_and_priority(self) -> None:
        ticket = create_support_ticket(
            self.session,
            self.customer_id,
            "Issue",
        )

        with self.assertRaisesRegex(ValueError, "Ticket status"):
            update_support_ticket(
                self.session,
                ticket.id,
                status="Unknown",
            )
        with self.assertRaisesRegex(ValueError, "Ticket priority"):
            update_support_ticket(
                self.session,
                ticket.id,
                priority="Urgent",
            )


if __name__ == "__main__":
    unittest.main()
