"""Tests for the PWA manifest + icon routes (Chrome 'Install app')."""
from fastapi.testclient import TestClient
from gnl_core.web.app import app

client = TestClient(app)


def test_manifest_served():
    r = client.get("/manifest.webmanifest")
    assert r.status_code == 200
    assert 'manifest' in r.headers.get('content-type', '')
    m = r.json()
    assert m['name'] == 'GNL Process'
    assert m['display'] == 'standalone'
    assert len(m['icons']) >= 1


def test_icon_served():
    r = client.get("/icons/gnl-icon-256.png")
    assert r.status_code == 200
    assert r.headers.get('content-type') == 'image/png'
    assert len(r.content) > 1000


def test_favicon_served():
    r = client.get("/favicon.ico")
    assert r.status_code == 200


def test_icon_path_traversal_blocked():
    r = client.get("/icons/..%2f..%2fapp.py")
    assert r.status_code == 404


def test_dashboard_links_manifest():
    r = client.get("/")
    assert '/manifest.webmanifest' in r.text
    assert 'rel="manifest"' in r.text
