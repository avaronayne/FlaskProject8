from app import app


def test_homepage():
    client = app.test_client()
    response = client.get("/")

    assert response.status_code == 200


def test_convert_route():
    client = app.test_client()

    response = client.post("/convert", data={
        "from_cur": "USD",
        "to_cur": "EUR",
        "amount": "100"
    })

    assert response.status_code == 200


def test_history_route():
    client = app.test_client()
    response = client.get("/history")

    assert response.status_code == 200


def test_save_route():
    client = app.test_client()

    response = client.post("/save", data={
        "from_cur": "USD",
        "to_cur": "EUR",
        "amount": "100",
        "result": "92"
    })

    assert response.status_code == 200


def test_invalid_amount():
    client = app.test_client()

    response = client.post("/convert", data={
        "from_cur": "USD",
        "to_cur": "EUR",
        "amount": "abc"
    })

    assert response.status_code == 200

def test_health_route():
    client = app.test_client()
    response = client.get("/health")

    assert response.status_code == 200
    assert b"status" in response.data

def test_api_currencies():
    client = app.test_client()
    response = client.get("/api/currencies")

    assert response.status_code == 200
    assert b"USD" in response.data

from unittest.mock import patch

@patch("app.get_all_rates")
def test_api_convert(mock_get_all_rates):
    mock_get_all_rates.return_value = (
        {
            "base": "USD",
            "date": "2026-04-10",
            "rates": {"EUR": 0.9, "USD": 1.0}
        },
        None
    )

    client = app.test_client()
    response = client.get("/api/convert?from=USD&to=EUR&amount=100")

    assert response.status_code == 200
    assert b"converted" in response.data