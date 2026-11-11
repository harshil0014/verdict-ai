"""Argon2id passwords and revocable, opaque, cloud-backed account sessions."""
import asyncio
import hashlib
import secrets
import os
from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from pwdlib import PasswordHash
from saas_store import repo, SESSION

COOKIE = "verdict_account_session"
passwords = PasswordHash.recommended()
HASH_SLOTS = asyncio.Semaphore(2)
DUMMY_HASH = passwords.hash(secrets.token_urlsafe(32))


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{2,31}$")
    password: str = Field(min_length=12, max_length=128)


class Registration(Credentials):
    display_name: str = Field(min_length=1, max_length=80)


class Recovery(Credentials):
    recovery_code: str = Field(min_length=20, max_length=100)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def cookie(response, token):
    response.set_cookie(COOKIE, token, httponly=True, secure=os.getenv("VERDICT_SECURE_COOKIES") == "true",
                        samesite="lax", max_age=30*86400, path="/")
    response.headers["Cache-Control"] = "private, no-store"


async def throttle(request, purpose, username="", limit=8, seconds=900):
    # Deliberately ignore untrusted forwarding headers for the security key.
    ip = request.client.host if request.client else "unknown"
    if purpose in ("login-user", "recover"):
        ip = "account"
    pepper = os.getenv("VERDICT_AUTH_PEPPER", "")
    if len(pepper) < 24:
        raise HTTPException(503, "Account security configuration is missing")
    key = token_hash(pepper + ":" + purpose + ":" + ip + ":" + username.lower())
    result = await repo.rpc("rate", {"key": key, "limit": limit, "seconds": seconds}, session="")
    if not result["allowed"]:
        raise HTTPException(429, "Too many attempts. Please try again later")


async def current_session(request: Request):
    raw = request.cookies.get(COOKIE, "")
    if not 32 <= len(raw) <= 128:
        raise HTTPException(401, "Sign in to continue")
    hashed = token_hash(raw)
    me = await repo.rpc("me", session=hashed)
    SESSION.set(hashed)
    return me


async def register(data, request, response):
    if not data.display_name.strip():
        raise HTTPException(422, "Enter your name")
    await throttle(request, "register", limit=10, seconds=3600)
    recovery, token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    async with HASH_SLOTS:
        hashed = await asyncio.to_thread(passwords.hash, data.password)
    me = await repo.rpc("register", {"username": data.username.lower(), "display_name": data.display_name.strip(),
        "password_hash": hashed, "recovery_hash": token_hash(recovery)}, session=token_hash(token))
    cookie(response, token)
    return {**me, "recovery_code": recovery}


async def login(data, request, response):
    await throttle(request, "login-ip", limit=40)
    await throttle(request, "login-user", data.username)
    row = await repo.rpc("login_lookup", {"username": data.username.lower()}, session="")
    async with HASH_SLOTS:
        valid, upgraded = await asyncio.to_thread(passwords.verify_and_update, data.password,
                                                  row["password_hash"] if row else DUMMY_HASH)
    if not row or not valid:
        raise HTTPException(401, "The username or password is incorrect")
    token = secrets.token_urlsafe(32)
    me = await repo.rpc("login_commit", {"username": data.username.lower(), "expected_hash": row["password_hash"],
        "upgraded_hash": upgraded}, session=token_hash(token))
    cookie(response, token)
    return me


async def recover(data, request, response):
    await throttle(request, "recover", data.username, limit=5)
    recovery, token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    async with HASH_SLOTS:
        hashed = await asyncio.to_thread(passwords.hash, data.password)
    me = await repo.rpc("recover", {"username": data.username.lower(), "recovery_hash": token_hash(data.recovery_code),
        "password_hash": hashed, "new_recovery_hash": token_hash(recovery)}, session=token_hash(token))
    cookie(response, token)
    return {**me, "recovery_code": recovery}
