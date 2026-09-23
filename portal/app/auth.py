"""Gitea-backed OAuth authentication for the Forge0 portal."""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, Request

SESSION_COOKIE = "forge0_session"
STATE_COOKIE = "forge0_oauth_state"
SESSION_MAX_AGE = 8 * 60 * 60
STATE_MAX_AGE = 10 * 60


@dataclass(frozen=True)
class AuthConfig:
    client_id: str
    client_secret: str
    session_secret: str
    redirect_uri: str
    public_gitea_url: str
    internal_gitea_url: str
    allowed_users: frozenset[str]

    @classmethod
    def from_env(cls) -> AuthConfig | None:
        client_id = os.getenv("GITEA_OAUTH_CLIENT_ID", "").strip()
        client_secret = os.getenv("GITEA_OAUTH_CLIENT_SECRET", "").strip()
        session_secret = os.getenv("FORGE0_SESSION_SECRET", "").strip()
        if not all((client_id, client_secret, session_secret)):
            return None
        allowed = frozenset(
            user.strip().casefold()
            for user in os.getenv("FORGE0_ALLOWED_USERS", "your-username").split(",")
            if user.strip()
        )
        return cls(
            client_id=client_id,
            client_secret=client_secret,
            session_secret=session_secret,
            redirect_uri=os.getenv(
                "FORGE0_OAUTH_REDIRECT_URI", "http://localhost:3001/auth/callback"
            ).strip(),
            public_gitea_url=os.getenv(
                "GITEA_PUBLIC_URL", "http://localhost:3001/gitea/"
            ).rstrip("/"),
            internal_gitea_url=os.getenv("GITEA_URL", "http://gitea:3000").rstrip("/"),
            allowed_users=allowed,
        )

    @property
    def secure_cookies(self) -> bool:
        return self.redirect_uri.startswith("https://")


def safe_next(value: str | None, default: str = "/") -> str:
    """Accept only local absolute paths as post-authentication destinations."""
    if not value or not value.startswith("/") or value.startswith("//"):
        return default
    if "\\" in value or any(character in value for character in ("\r", "\n", "\0")):
        return default
    return value


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def sign(payload: dict[str, object], secret: str) -> str:
    body = _encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    signature = _encode(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{signature}"


def unsign(value: str, secret: str, max_age: int) -> dict[str, object] | None:
    try:
        body, signature = value.split(".", 1)
        expected = _encode(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(_decode(body))
        issued_at = int(payload["iat"])
        now = int(time.time())
        if issued_at > now + 60 or now - issued_at > max_age:
            return None
        return payload
    except (ValueError, TypeError, KeyError, UnicodeDecodeError, binascii.Error, json.JSONDecodeError):
        return None


def current_user(request: Request, config: AuthConfig) -> dict[str, object] | None:
    raw = request.cookies.get(SESSION_COOKIE, "")
    payload = unsign(raw, config.session_secret, SESSION_MAX_AGE) if raw else None
    if not payload or not isinstance(payload.get("login"), str):
        return None
    if str(payload["login"]).casefold() not in config.allowed_users:
        return None
    return payload


def authorization(config: AuthConfig, destination: str) -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = _encode(hashlib.sha256(verifier.encode()).digest())
    state_id = secrets.token_urlsafe(24)
    state_cookie = sign(
        {"iat": int(time.time()), "next": safe_next(destination), "nonce": state_id, "verifier": verifier},
        config.session_secret,
    )
    query = urlencode(
        {
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "response_type": "code",
            "scope": "openid profile email",
            "state": state_id,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{config.public_gitea_url}/login/oauth/authorize?{query}", state_cookie


async def exchange_code(config: AuthConfig, code: str, verifier: str) -> dict[str, object]:
    async with httpx.AsyncClient(timeout=15, verify=False) as client:
        token_response = await client.post(
            f"{config.internal_gitea_url}/login/oauth/access_token",
            data={
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": config.redirect_uri,
                "code_verifier": verifier,
            },
            headers={"Accept": "application/json"},
        )
        if token_response.is_error:
            raise HTTPException(status_code=401, detail="Gitea rejected the authorization code")
        access_token = token_response.json().get("access_token")
        if not access_token:
            raise HTTPException(status_code=401, detail="Gitea did not return an access token")
        user_response = await client.get(
            f"{config.internal_gitea_url}/login/oauth/userinfo",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )
        if user_response.is_error:
            raise HTTPException(status_code=401, detail="Gitea identity lookup failed")
        return user_response.json()


def normalize_identity(identity: dict[str, object], config: AuthConfig) -> dict[str, object]:
    login = identity.get("preferred_username") or identity.get("login") or identity.get("name")
    if not isinstance(login, str) or not login.strip():
        raise HTTPException(status_code=401, detail="Gitea identity has no username")
    login = login.strip()
    if login.casefold() not in config.allowed_users:
        raise HTTPException(status_code=403, detail="This Gitea account is not allowed to use Forge0")
    return {
        "login": login,
        "name": identity.get("name") if isinstance(identity.get("name"), str) else login,
        "email": identity.get("email") if isinstance(identity.get("email"), str) else "",
        "iat": int(time.time()),
    }
