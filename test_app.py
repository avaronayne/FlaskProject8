from app import app


def test_homepage():
    client = app.test_client()
    response = client.get("/")

    assert response.status_code == 200


def test_convert_route():
    client = app.test_client()

    response = client.post("/convert", data={
        "from_currency": "USD",
        "to_currency": "EUR",
        "amount": 100
    })

    assert response.status_code == 200


def test_history_route():
    client = app.test_client()
    response = client.get("/history")

    assert response.status_code == 200


def test_save_route():
    client = app.test_client()

    response = client.post("/save", data={
        "from_currency": "USD",
        "to_currency": "EUR",
        "amount": 100,
        "result": 92
    })

    assert response.status_code == 200


def test_invalid_amount():
    client = app.test_client()

    response = client.post("/convert", data={
        "from_currency": "USD",
        "to_currency": "EUR",
        "amount": "abc"
    })

    assert response.status_code == 200