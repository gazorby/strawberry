from starlite import status_codes


def test_returns_error_when_missing_query(test_client):
    response = test_client.post("/graphql", json={})

    assert response.status_code == status_codes.HTTP_400_BAD_REQUEST


def test_returns_error_when_not_sending_wrong_content_type(test_client):
    response = test_client.post("/graphql", data="Example")

    assert response.status_code == status_codes.HTTP_415_UNSUPPORTED_MEDIA_TYPE
