import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.connection import Base, get_db
from app.database.models import Customer, Order, SupportTicket
from app.main import app, get_support_workflow


class FakeWorkflow:
    def invoke(self, state: dict[str, object]) -> dict[str, object]:
        needs_human = state["message"] == "escalate"
        return {
            "intent": "general_query",
            "answer": "Human review requested." if needs_human else "Policy answer.",
            "sources": [] if needs_human else ["payment_faq.txt"],
            "needs_human": needs_human,
        }


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.environment = patch.dict(
            os.environ,
            {
                "AUTH_SECRET_KEY": "test-auth-secret-not-for-production-32",
                "CUSTOMER_TOKEN_ADMIN_KEY": "test-admin-key-for-api-verification",
            },
        )
        self.environment.start()
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.testing_session_factory = sessionmaker(
            bind=self.engine,
            class_=Session,
            expire_on_commit=False,
        )

        with self.testing_session_factory() as db:
            first = Customer(name="First Customer", email="first@example.com")
            second = Customer(name="Second Customer", email="second@example.com")
            db.add_all([first, second])
            db.commit()
            db.refresh(first)
            db.refresh(second)
            self.customer_id = first.id
            self.other_customer_id = second.id
            own_order = Order(
                customer_id=first.id,
                product="Own item",
                amount=10,
                status="Processing",
            )
            other_order = Order(
                customer_id=second.id,
                product="Other item",
                amount=20,
                status="Shipped",
            )
            own_ticket = SupportTicket(
                customer_id=first.id,
                issue="Own ticket",
                priority="Medium",
                status="Open",
            )
            other_ticket = SupportTicket(
                customer_id=second.id,
                issue="Other ticket",
                priority="Medium",
                status="Open",
            )
            db.add_all([own_order, other_order, own_ticket, other_ticket])
            db.commit()
            db.refresh(own_order)
            db.refresh(other_order)
            db.refresh(own_ticket)
            self.order_id = own_order.id
            self.other_order_id = other_order.id
            self.ticket_id = own_ticket.id

        def override_get_db():
            with self.testing_session_factory() as db:
                yield db

        self.workflow = FakeWorkflow()
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_support_workflow] = lambda: self.workflow
        self.client = TestClient(app)
        token_response = self.client.post(
            "/auth/token",
            headers={"X-Admin-Key": "test-admin-key-for-api-verification"},
            json={"customer_id": self.customer_id},
        )
        self.assertEqual(token_response.status_code, 200)
        self.customer_headers = {
            "Authorization": f"Bearer {token_response.json()['access_token']}"
        }

    def tearDown(self) -> None:
        self.client.close()
        app.dependency_overrides.clear()
        self.engine.dispose()
        self.environment.stop()

    def test_chat_requires_customer_authentication(self) -> None:
        response = self.client.post("/chat", json={"message": "hello"})

        self.assertEqual(response.status_code, 401)

    def test_orders_require_a_valid_customer_token(self) -> None:
        missing_token = self.client.get(f"/orders/{self.order_id}")
        invalid_token = self.client.get(
            f"/orders/{self.order_id}",
            headers={"Authorization": "Bearer invalid-token"},
        )

        self.assertEqual(missing_token.status_code, 401)
        self.assertEqual(invalid_token.status_code, 401)

    def test_customer_token_issuance_requires_admin_key(self) -> None:
        response = self.client.post(
            "/auth/token",
            json={"customer_id": self.customer_id},
        )

        self.assertEqual(response.status_code, 403)

    def test_customer_creation_requires_admin_key(self) -> None:
        missing_admin = self.client.post(
            "/customers",
            json={"name": "Unauthorized", "email": "unauthorized@example.com"},
        )
        wrong_admin = self.client.post(
            "/customers",
            headers={"X-Admin-Key": "wrong-key"},
            json={"name": "Unauthorized", "email": "unauthorized@example.com"},
        )

        self.assertEqual(missing_admin.status_code, 403)
        self.assertEqual(wrong_admin.status_code, 403)

    def test_ticket_update_rejects_invalid_status_and_priority(self) -> None:
        invalid_status = self.client.patch(
            f"/tickets/{self.ticket_id}",
            headers={"X-Admin-Key": "test-admin-key-for-api-verification"},
            json={"status": "Unknown"},
        )
        invalid_priority = self.client.patch(
            f"/tickets/{self.ticket_id}",
            headers={"X-Admin-Key": "test-admin-key-for-api-verification"},
            json={"priority": "Urgent"},
        )

        self.assertEqual(invalid_status.status_code, 422)
        self.assertEqual(invalid_priority.status_code, 422)

    def test_chat_saves_history_for_authenticated_customer(self) -> None:
        response = self.client.post(
            "/chat",
            headers=self.customer_headers,
            json={"message": "hello"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sources"], ["payment_faq.txt"])

        history = self.client.get(
            f"/chat/history/{self.customer_id}",
            headers=self.customer_headers,
        )
        self.assertEqual(history.status_code, 200)
        self.assertEqual(
            [message["role"] for message in history.json()["messages"]],
            ["user", "assistant"],
        )

    def test_customer_cannot_read_other_customer_order_or_history(self) -> None:
        order_response = self.client.get(
            f"/orders/{self.other_order_id}",
            headers=self.customer_headers,
        )
        history_response = self.client.get(
            f"/chat/history/{self.other_customer_id}",
            headers=self.customer_headers,
        )

        self.assertEqual(order_response.status_code, 404)
        self.assertEqual(history_response.status_code, 404)

    def test_ticket_access_is_customer_scoped_and_update_is_admin_only(self) -> None:
        own_tickets = self.client.get(
            "/tickets",
            headers=self.customer_headers,
        )
        cross_customer_ticket = self.client.post(
            "/tickets",
            headers=self.customer_headers,
            json={
                "customer_id": self.other_customer_id,
                "issue": "Should not be created",
            },
        )
        unauthenticated_update = self.client.patch(
            f"/tickets/{self.ticket_id}",
            json={"status": "Resolved"},
        )
        admin_update = self.client.patch(
            f"/tickets/{self.ticket_id}",
            headers={"X-Admin-Key": "test-admin-key-for-api-verification"},
            json={"status": "Resolved"},
        )

        self.assertEqual(len(own_tickets.json()), 1)
        self.assertEqual(cross_customer_ticket.status_code, 404)
        self.assertEqual(unauthenticated_update.status_code, 403)
        self.assertEqual(admin_update.status_code, 200)
        self.assertEqual(admin_update.json()["status"], "Resolved")

    def test_chat_escalation_is_recorded_and_admin_can_resolve(self) -> None:
        chat_response = self.client.post(
            "/chat",
            headers=self.customer_headers,
            json={"message": "escalate"},
        )
        escalation_id = chat_response.json()["escalation_id"]
        approval = self.client.patch(
            f"/escalations/{escalation_id}",
            headers={"X-Admin-Key": "test-admin-key-for-api-verification"},
            json={"status": "approved"},
        )
        duplicate_review = self.client.patch(
            f"/escalations/{escalation_id}",
            headers={"X-Admin-Key": "test-admin-key-for-api-verification"},
            json={"status": "resolved"},
        )

        self.assertEqual(chat_response.status_code, 200)
        self.assertTrue(chat_response.json()["needs_human"])
        self.assertEqual(approval.status_code, 200)
        self.assertEqual(approval.json()["status"], "approved")
        self.assertEqual(duplicate_review.status_code, 409)

        escalations = self.client.get(
            "/escalations",
            headers=self.customer_headers,
        )
        self.assertEqual(escalations.status_code, 200)
        self.assertEqual(escalations.json()[0]["status"], "approved")

    def test_health_endpoint_checks_database(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["database"], "ok")
        self.assertTrue(response.headers["X-Request-ID"])

    def test_request_id_header_is_preserved(self) -> None:
        response = self.client.get(
            "/health",
            headers={"X-Request-ID": "test-request-id"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Request-ID"], "test-request-id")


if __name__ == "__main__":
    unittest.main()
