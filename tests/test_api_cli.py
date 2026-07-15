import pytest

from vibecheck.cli import main
from vibecheck.mockdata import generate, generate_events


def test_cli_demo_runs(capsys):
    rc = main(["demo", "--count", "300", "--top", "5"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "roadmap" in out.lower()


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0


def test_mockdata_deterministic():
    a = [t.text for t in generate(50, seed=1)]
    b = [t.text for t in generate(50, seed=1)]
    assert a == b
    assert list(generate_events(3, seed=1))[0].keys() >= {"text", "source", "channel"}


def test_api_endpoints(tmp_path):
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from vibecheck.services.api import create_app

    app = create_app(db=str(tmp_path / "api.db"))
    client = TestClient(app)

    assert client.get("/health").json()["status"] == "ok"

    # ingest a batch, run analysis, read the roadmap
    msgs = [t.text for t in generate(200, seed=9)]
    r = client.post("/ingest", json={"messages": msgs})
    assert r.status_code == 200
    assert r.json()["accepted"] > 0

    assert client.post("/analyze").json()["clusters"] >= 0
    roadmap = client.get("/roadmap?top=5").json()
    assert isinstance(roadmap, list)

    metrics = client.get("/metrics").text
    assert "vibecheck_tickets_ingested_total" in metrics

    # dashboard HTML is served at /
    assert "VibeCheck" in client.get("/").text


def test_api_webhook_noise(tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from vibecheck.services.api import create_app

    client = TestClient(create_app(db=str(tmp_path / "wh.db")))
    assert client.post("/webhook", json={"text": "Thanks!"}).json()["accepted"] is False
    assert client.post("/webhook", json={"text": "the export button returns a 404 error"}).json()["accepted"] is True
