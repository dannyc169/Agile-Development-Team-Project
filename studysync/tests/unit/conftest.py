import os

import pytest

from app import create_app, db
import os
os.environ.setdefault("SECRET_KEY", "test-secret-key")

@pytest.fixture()
def app(tmp_path):
    db_path = tmp_path / "test.db"

    test_app = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
            "SECRET_KEY": "test-secret-key",
        }
    )

    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()
        db.engine.dispose()

    if db_path.exists():
        os.remove(db_path)


@pytest.fixture()
def client(app):
    with app.test_client() as client:
        yield client
