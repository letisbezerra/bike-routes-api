from sqlalchemy import text

from app.shared.database import get_db


def test_get_db_yields_working_session():
    db = next(get_db())
    try:
        result = db.execute(text("SELECT 1")).scalar()
        assert result == 1
    finally:
        db.close()
