import os
import asyncio
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from itsdangerous import SignatureExpired
from itsdangerous import URLSafeTimedSerializer

from app.core.security import (
    auth_configuration_status,
    issue_customer_token,
    read_customer_token,
    verify_admin_key,
)


class SecurityTests(unittest.TestCase):
    def test_application_lifespan_rejects_missing_auth_config(self) -> None:
        from app.main import lifespan

        async def exercise() -> None:
            with patch.dict(os.environ, {}, clear=True):
                async with lifespan(object()):
                    pass

        with self.assertRaises(HTTPException) as caught:
            asyncio.run(exercise())

        self.assertEqual(caught.exception.status_code, 503)
    def test_runtime_auth_status_reports_secure_configuration(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AUTH_SECRET_KEY": "A" * 32,
                "CUSTOMER_TOKEN_ADMIN_KEY": "B" * 32,
            },
            clear=True,
        ):
            status = auth_configuration_status()

        self.assertTrue(status["customer_auth_configured"])
        self.assertTrue(status["admin_auth_configured"])

    def test_missing_auth_secret_is_rejected(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(HTTPException) as caught:
                issue_customer_token(1)

        self.assertEqual(caught.exception.status_code, 503)

    def test_short_auth_secret_is_rejected(self) -> None:
        with patch.dict(
            os.environ,
            {"AUTH_SECRET_KEY": "too-short"},
            clear=True,
        ):
            with self.assertRaises(HTTPException) as caught:
                issue_customer_token(1)

        self.assertEqual(caught.exception.status_code, 503)

    def test_valid_token_contains_customer_id_and_rejects_invalid_token(self) -> None:
        environment = {
            "AUTH_SECRET_KEY": "A" * 32,
        }
        with patch.dict(os.environ, environment, clear=True):
            token = issue_customer_token(42)
            self.assertEqual(read_customer_token(token), 42)

            with self.assertRaises(HTTPException) as caught:
                read_customer_token("not-a-valid-token")

        self.assertEqual(caught.exception.status_code, 401)

    def test_missing_admin_key_is_rejected(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(HTTPException) as caught:
                verify_admin_key("any-key")

        self.assertEqual(caught.exception.status_code, 503)

    def test_expired_token_is_rejected(self) -> None:
        secret = "C" * 32
        with patch.dict(
            os.environ,
            {"AUTH_SECRET_KEY": secret},
            clear=True,
        ):
            token = issue_customer_token(42)
            serializer = URLSafeTimedSerializer(
                secret,
                salt="customer-support-access-token",
            )
            with self.assertRaises(SignatureExpired):
                serializer.loads(token, max_age=-1)

    def test_read_customer_token_rejects_expired_token(self) -> None:
        secret = "D" * 32
        with patch.dict(
            os.environ,
            {"AUTH_SECRET_KEY": secret},
            clear=True,
        ):
            serializer = URLSafeTimedSerializer(
                secret,
                salt="customer-support-access-token",
            )
            expired_token = serializer.dumps({"customer_id": 42})
            with patch(
                "app.core.security.URLSafeTimedSerializer.loads",
                side_effect=SignatureExpired("expired"),
            ):
                with self.assertRaises(HTTPException) as caught:
                    read_customer_token(expired_token)

        self.assertEqual(caught.exception.status_code, 401)

    def test_wrong_admin_key_is_rejected(self) -> None:
        with patch.dict(
            os.environ,
            {"CUSTOMER_TOKEN_ADMIN_KEY": "B" * 32},
            clear=True,
        ):
            with self.assertRaises(HTTPException) as caught:
                verify_admin_key("wrong-key")

        self.assertEqual(caught.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
