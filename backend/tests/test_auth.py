import jwt

from app.api.auth import create_session_token, password_hash, settings


def test_passwords_are_hashed_and_verified() -> None:
    encoded = password_hash.hash("correct-horse-battery-staple")
    assert encoded != "correct-horse-battery-staple"
    assert password_hash.verify("correct-horse-battery-staple", encoded)
    assert not password_hash.verify("incorrect-password", encoded)


def test_session_token_contains_user_identity_and_expiration() -> None:
    token = create_session_token(42)
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    assert payload["sub"] == "42"
    assert payload["exp"] > payload["iat"]
