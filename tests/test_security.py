from app import create_app
from services import reviews


def test_oversized_review_rejected():
    client = create_app().test_client()
    response = client.post('/reviews', data={'message': 'x' * (65 * 1024)})
    assert response.status_code == 413


def test_forwarded_header_cannot_choose_rate_limit_identity(monkeypatch):
    observed = []
    def capture(**kwargs):
        observed.append(kwargs['ip'])
        return {'id': 'test'}, None
    monkeypatch.setattr(reviews, 'add_review', capture)
    client = create_app().test_client()
    for address in ['198.51.100.1', '198.51.100.2']:
        response = client.post('/reviews', data={}, headers={'X-Forwarded-For': address})
        assert response.status_code == 302
    assert observed == ['127.0.0.1', '127.0.0.1']


def test_no_public_fallback_signing_key(monkeypatch):
    monkeypatch.delenv('SECRET_KEY', raising=False)
    first, second = create_app(), create_app()
    assert len(first.secret_key) >= 32
    assert first.secret_key != second.secret_key
