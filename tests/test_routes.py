"""Every public route returns 200 (/metrics is private); unknown paths return 404."""
from __future__ import annotations

from tests.helpers import public_get_rules


def test_public_routes_return_200(client, app):
    missing = []
    checked = []
    for rule in public_get_rules(app):
        if "<" in rule.rule:
            if rule.endpoint == "data":
                for name in ("catalog.json", "trailers.json"):
                    path = f"/data/{name}"
                    resp = client.get(path)
                    checked.append(path)
                    if resp.status_code != 200:
                        missing.append((path, resp.status_code))
            continue
        if rule.endpoint == "metrics":
            continue  # private: token-gated, covered in tests/test_app.py
        resp = client.get(rule.rule)
        checked.append(rule.rule)
        if resp.status_code != 200:
            missing.append((rule.rule, resp.status_code))
    assert checked, "url_map produced no concrete GET routes to check"
    assert not missing, f"routes did not return 200: {missing}"


def test_unknown_path_returns_404(client):
    resp = client.get("/this-path-should-not-exist-qa-404")
    assert resp.status_code == 404
    body = resp.get_data(as_text=True)
    assert "not" in body.lower() or "found" in body.lower() or "2DayMovie" in body


def test_unknown_public_data_file_returns_404(client):
    """Non-allowlisted /data/* names 404. catalog_sources is in test_exposure.py."""
    assert client.get("/data/does-not-exist.json").status_code == 404
