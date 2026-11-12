from sqlalchemy import func, select

from app.models import User
from app.seed.run import run_seed


def test_seed_creates_accounts_and_is_idempotent(db_session) -> None:
    run_seed()
    count1 = db_session.scalar(select(func.count()).select_from(User))
    assert count1 >= 7
    tamara = db_session.scalar(select(User).where(User.username == "tamara"))
    assert tamara is not None
    run_seed()
    count2 = db_session.scalar(select(func.count()).select_from(User))
    assert count2 == count1
