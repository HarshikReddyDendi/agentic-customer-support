import os
from hmac import compare_digest

from dotenv import load_dotenv
from fastapi import Header, HTTPException, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

load_dotenv()

TOKEN_MAX_AGE_SECONDS = 60 * 60
TOKEN_SALT = "customer-support-access-token"
MIN_SECRET_LENGTH = 32


def validate_auth_configuration() -> None:
    auth_secret = os.getenv("AUTH_SECRET_KEY", "").strip()
    admin_key = os.getenv("CUSTOMER_TOKEN_ADMIN_KEY", "").strip()

    if not auth_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Customer authentication is not configured",
        )
    if len(auth_secret) < MIN_SECRET_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AUTH_SECRET_KEY must contain at least 32 characters",
        )
    if not admin_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Administrative API access is not configured",
        )
    if len(admin_key) < MIN_SECRET_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CUSTOMER_TOKEN_ADMIN_KEY must contain at least 32 characters",
        )


def auth_configuration_status() -> dict[str, bool]:
    auth_secret = os.getenv("AUTH_SECRET_KEY", "").strip()
    admin_key = os.getenv("CUSTOMER_TOKEN_ADMIN_KEY", "").strip()
    return {
        "customer_auth_configured": (
            len(auth_secret) >= MIN_SECRET_LENGTH
        ),
        "admin_auth_configured": (
            len(admin_key) >= MIN_SECRET_LENGTH
        ),
    }


def _serializer() -> URLSafeTimedSerializer:
    secret = os.getenv("AUTH_SECRET_KEY", "").strip()
    if len(secret) < MIN_SECRET_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Customer authentication is not configured securely",
        )
    return URLSafeTimedSerializer(secret, salt=TOKEN_SALT)


def issue_customer_token(customer_id: int) -> str:
    return _serializer().dumps({"customer_id": customer_id})


def read_customer_token(token: str) -> int:
    try:
        payload = _serializer().loads(
            token,
            max_age=TOKEN_MAX_AGE_SECONDS,
        )
    except (SignatureExpired, BadSignature) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired customer token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    customer_id = payload.get("customer_id") if isinstance(payload, dict) else None
    if isinstance(customer_id, bool) or not isinstance(customer_id, int):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid customer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return customer_id


def verify_admin_key(
    x_admin_key: str | None = Header(default=None),
) -> None:
    configured_key = os.getenv("CUSTOMER_TOKEN_ADMIN_KEY", "").strip()
    if len(configured_key) < MIN_SECRET_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Administrative API access is not configured securely",
        )
    if x_admin_key is None or not compare_digest(x_admin_key, configured_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative access is required",
        )
