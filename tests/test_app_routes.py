from fastapi.testclient import TestClient

from voice_rag_agent.app import app

# No "with" block, so the lifespan (Claude client, retriever) never starts.
client = TestClient(app)


def test_replays_are_served_from_an_allowlist():
    for lang in ("en", "es"):
        r = client.get(f"/replays/{lang}.json")
        assert r.status_code == 200
        assert r.json()["turns"]
    assert client.get("/replays/fr.json").status_code == 404
    assert client.get("/replays/..%2Fapp.json").status_code == 404
