from app.db.session import get_db
from app.main import app


def test_health_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["db"] == "ok"


def test_health_db_down(client):
    class BrokenSession:
        def execute(self, *args, **kwargs):
            raise RuntimeError("db unavailable")

    app.dependency_overrides[get_db] = lambda: BrokenSession()

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["db"] == "down"
