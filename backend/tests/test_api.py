import asyncio
from typing import cast
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_is_live_without_supabase_configuration() -> None:
    response = client.get("/health", headers={"X-Request-ID": "test-request-1"})

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"] == {"status": "ok"}
    assert response.json()["requestId"] == "test-request-1"
    assert response.headers["X-Request-ID"] == "test-request-1"


def test_versioned_health_endpoint() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ok"


def test_web_app_assets_are_served_without_changing_api_not_found_responses(tmp_path, monkeypatch) -> None:
    from app import main
    from fastapi.staticfiles import StaticFiles

    (tmp_path / "index.html").write_text("<!doctype html><title>VitaPulse</title>", encoding="utf-8")
    (tmp_path / "styles.css").write_text("body { color: black; }", encoding="utf-8")
    monkeypatch.setattr(main, "web_static_files", StaticFiles(directory=tmp_path, html=True))

    page = client.get("/")
    stylesheet = client.get("/styles.css")
    missing_api = client.get("/api/v1/not-a-route")

    assert page.status_code == 200
    assert "<title>VitaPulse</title>" in page.text
    assert stylesheet.status_code == 200
    assert stylesheet.text == "body { color: black; }"
    assert missing_api.status_code == 404
    assert missing_api.json()["error"]["code"] == "NOT_FOUND"


def test_protected_endpoint_requires_a_bearer_token() -> None:
    response = client.get("/api/v1/me")

    assert response.status_code == 401
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert "Traceback" not in response.text


def test_health_endpoints_require_an_authenticated_athlete() -> None:
    for path in (
        "/api/v1/health/overview",
        "/api/v1/health/medical-reports",
        "/api/v1/health/biomarkers",
        "/api/v1/health/body-map",
    ):
        response = client.get(path)

        assert response.status_code == 401
        assert response.json()["success"] is False


def test_rehab_endpoints_require_an_authenticated_athlete() -> None:
    for path in (
        "/api/v1/rehab/dashboard",
        "/api/v1/rehab/today",
        "/api/v1/rehab/program",
        "/api/v1/rehab/exercises",
        "/api/v1/rehab/sessions",
        "/api/v1/rehab/movement/summary",
        "/api/v1/rehab/progress",
        "/api/v1/rehab/functional-tests",
        "/api/v1/rehab/readiness/current",
        "/api/v1/rehab/return-to-sport",
        "/api/v1/rehab/history",
        "/api/v1/rehab/reports",
        "/api/v1/devices",
        "/api/v1/ml/models",
        "/api/v1/ml/movement-summary",
    ):
        response = client.get(path)
        assert response.status_code == 401, path
        assert response.json()["success"] is False


def test_ready_reports_missing_identity_configuration_without_leaking_values(monkeypatch) -> None:
    from app import main
    from app.core.config import Settings

    monkeypatch.setattr(
        main,
        "settings",
        Settings(supabase_url="", supabase_publishable_key=""),
    )
    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert "SUPABASE" not in response.text


def test_pending_doctor_applicant_cannot_use_the_athlete_api(monkeypatch) -> None:
    import asyncio

    from app.core import security
    from app.core.config import Settings
    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload
            self.status_code = 200

        def json(self):
            return self.payload

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, **_kwargs):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, url, **_kwargs):
            if url.endswith("/auth/v1/user"):
                return FakeResponse({"id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"})
            if url.endswith("/rest/v1/profiles"):
                return FakeResponse([{"role": "ATHLETE", "display_name": "Pending doctor"}])
            return FakeResponse([{"status": "PENDING"}])

    monkeypatch.setattr(security.httpx, "AsyncClient", FakeClient)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-token")
    settings = Settings(
        supabase_url="https://supabase.example.test",
        supabase_publishable_key="publishable-test-key",
    )

    try:
        asyncio.run(security.get_current_profile(credentials, settings))
    except HTTPException as error:
        assert error.status_code == 403
        assert "Doctor access applications" in error.detail
    else:
        raise AssertionError("A pending doctor applicant must not be authenticated as an athlete.")


def test_report_object_is_restored_if_database_delete_fails(monkeypatch) -> None:
    from app.api.v1 import health
    from app.core.config import Settings
    from app.repositories.supabase import SupabaseRepository

    events = []
    report_id = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    athlete_id = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")

    class FakeRepository:
        def __init__(self, *_args):
            pass

        async def get(self, _report_id):
            return {
                "processing_status": "COMPLETED",
                "storage_bucket": "medical-reports",
                "storage_path": f"{athlete_id}/{report_id}.pdf",
                "mime_type": "application/pdf",
            }

        async def delete(self, _report_id):
            events.append("database-delete")
            raise RuntimeError("simulated database failure")

    class FakeStorage:
        async def download_object(self, *_args):
            events.append("download")
            return b"private source"

        async def delete_object(self, *_args):
            events.append("storage-delete")

        async def upload_object(self, *_args):
            events.append("restore")

    monkeypatch.setattr(health, "MedicalReportRepository", FakeRepository)

    with pytest.raises(RuntimeError, match="simulated database failure"):
        asyncio.run(
            health.delete_medical_report(
                report_id,
                (athlete_id, Settings(), cast(SupabaseRepository, FakeStorage())),
            )
        )

    assert events == ["download", "storage-delete", "database-delete", "restore"]
