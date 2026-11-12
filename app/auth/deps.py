from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, UserRole


def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = db.get(User, user_id)
    return user


def require_login(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    user = get_current_user(request, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется вход")
    return user


def require_role(*roles: UserRole) -> Callable[..., User]:
    def _dep(
        user: Annotated[User, Depends(require_login)],
    ) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
        return user

    return _dep


RequireMemberOrAdmin = Annotated[User, Depends(require_role(UserRole.member, UserRole.admin))]
RequireAdmin = Annotated[User, Depends(require_role(UserRole.admin))]
