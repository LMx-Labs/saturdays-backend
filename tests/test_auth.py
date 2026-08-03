import pytest
from httpx import AsyncClient

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


@pytest.mark.asyncio
async def test_argon2id_password_hashing():
    pwd = "SecretPassword123!"
    hashed = hash_password(pwd)

    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


@pytest.mark.asyncio
async def test_jwt_tokens():
    sub = "018f3a9b-7c1d-7000-8000-000000000001"
    role = "Customer"

    access_token = create_access_token(subject=sub, role=role)
    refresh_token = create_refresh_token(subject=sub)

    decoded_access = decode_token(access_token)
    assert decoded_access["sub"] == sub
    assert decoded_access["role"] == role
    assert decoded_access["type"] == "access"

    decoded_refresh = decode_token(refresh_token)
    assert decoded_refresh["sub"] == sub
    assert decoded_refresh["type"] == "refresh"


@pytest.mark.asyncio
async def test_user_registration_flow(client: AsyncClient):
    payload = {
        "email": "testuser@saturdays.com",
        "password": "Password123!",
        "role": "Customer",
    }

    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] == "testuser@saturdays.com"
    assert data["user"]["role"] == "Customer"
    assert data["user"]["is_active"] is True


@pytest.mark.asyncio
async def test_user_registration_duplicate_email(client: AsyncClient):
    payload = {
        "email": "duplicate@saturdays.com",
        "password": "Password123!",
    }

    res1 = await client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    duplicate_payload = {
        "email": "DUPLICATE@saturdays.com",
        "password": "Password123!",
    }
    res2 = await client.post("/api/v1/auth/register", json=duplicate_payload)
    assert res2.status_code == 409
    err = res2.json()
    assert err["error_code"] == "EMAIL_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_user_login_flow(client: AsyncClient):
    reg_payload = {
        "email": "loginuser@saturdays.com",
        "password": "MySecretPassword123",
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    login_payload = {
        "email": "loginuser@saturdays.com",
        "password": "MySecretPassword123",
    }
    res = await client.post("/api/v1/auth/login", json=login_payload)
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["email"] == "loginuser@saturdays.com"

    bad_login = {
        "email": "loginuser@saturdays.com",
        "password": "WrongPassword123",
    }
    res_bad = await client.post("/api/v1/auth/login", json=bad_login)
    assert res_bad.status_code == 401
    assert res_bad.json()["error_code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_refresh_token_flow(client: AsyncClient):
    reg_payload = {
        "email": "refreshuser@saturdays.com",
        "password": "Password123!",
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    refresh_token = reg_res.json()["refresh_token"]

    refresh_res = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_res.status_code == 200
    data = refresh_res.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_me_endpoint_flow(client: AsyncClient):
    reg_payload = {
        "email": "meuser@saturdays.com",
        "password": "Password123!",
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    access_token = reg_res.json()["access_token"]

    headers = {"Authorization": f"Bearer {access_token}"}
    res = await client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 200
    user_data = res.json()
    assert user_data["email"] == "meuser@saturdays.com"
