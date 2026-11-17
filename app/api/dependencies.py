from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.crud import get_customer_by_id
from app.database.models import Customer
from app.core.security import read_customer_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_customer(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> Customer:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Customer bearer token is required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    customer_id = read_customer_token(credentials.credentials)
    customer = get_customer_by_id(db, customer_id)
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token customer no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return customer
