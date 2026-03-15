"""
providers/oauth.py — Device-code OAuth flows for providers that support it.
Currently: Qwen (qwen-portal) with PKCE.
Token storage: ~/.sonder/tokens/{provider}.json
"""
import asyncio
import base64
import hashlib
import json
import os
import time
import uuid
import webbrowser
from pathlib import Path
from urllib.parse import urlencode

import httpx

TOKEN_DIR = Path.home() / ".sonder" / "tokens"
TOKEN_DIR.mkdir(parents=True, exist_ok=True)

OAUTH_PROVIDERS: dict[str, dict] = {
    "qwen-portal": {
        "display_name":    "Qwen",
        "device_code_url": "https://chat.qwen.ai/api/v1/oauth2/device/code",
        "token_url":       "https://chat.qwen.ai/api/v1/oauth2/token",
        "base_url":        "https://portal.qwen.ai/v1",
        "client_id":       "f0304373b74a44d2b584a3fb70ca9e56",
        "scope":           "openid profile email model.completion",
        "grant_type":      "urn:ietf:params:oauth:grant-type:device_code",
    },
}


# ── PKCE helpers ──────────────────────────────────────────────────────────────

def _pkce_pair() -> tuple[str, str]:
    """Return (verifier, challenge) for S256 PKCE."""
    verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


# ── Token storage ─────────────────────────────────────────────────────────────

def _token_path(provider: str) -> Path:
    return TOKEN_DIR / f"{provider}.json"


def load_token(provider: str) -> dict | None:
    p = _token_path(provider)
    return json.loads(p.read_text()) if p.exists() else None


def save_token(provider: str, token: dict):
    _token_path(provider).write_text(json.dumps(token, indent=2))


def get_access_token(provider: str) -> str | None:
    """Return a valid access token, refreshing if needed."""
    token = load_token(provider)
    if not token:
        return None
    if token.get("expires", 0) > time.time() * 1000 + 60_000:
        return token["access"]
    refreshed = _try_refresh(provider, token.get("refresh", ""))
    return refreshed


def _try_refresh(provider: str, refresh_token: str) -> str | None:
    cfg = OAUTH_PROVIDERS.get(provider)
    if not cfg or not refresh_token:
        return None
    try:
        r = httpx.post(
            cfg["token_url"],
            content=urlencode({
                "grant_type":    "refresh_token",
                "refresh_token": refresh_token,
                "client_id":     cfg["client_id"],
            }).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
            timeout=10,
        )
        data = r.json()
        if data.get("access_token"):
            token = {
                "access":  data["access_token"],
                "refresh": data.get("refresh_token", refresh_token),
                "expires": int(time.time() * 1000) + data.get("expires_in", 3600) * 1000,
            }
            save_token(provider, token)
            return token["access"]
    except Exception:
        pass
    return None


# ── Device-code login ─────────────────────────────────────────────────────────

async def login(provider: str) -> bool:
    """Run device-code + PKCE OAuth flow. Returns True on success."""
    cfg = OAUTH_PROVIDERS.get(provider)
    if not cfg:
        print(f"OAuth not supported for {provider}")
        return False

    verifier, challenge = _pkce_pair()

    # Step 1: request device code
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            cfg["device_code_url"],
            content=urlencode({
                "client_id":             cfg["client_id"],
                "scope":                 cfg["scope"],
                "code_challenge":        challenge,
                "code_challenge_method": "S256",
            }).encode(),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept":       "application/json",
                "x-request-id": str(uuid.uuid4()),
            },
        )

    if not r.is_success:
        print(f"  Device code request failed: {r.status_code} {r.text[:200]}")
        return False

    data = r.json()
    device_code    = data.get("device_code", "")
    user_code      = data.get("user_code", "")
    verify_uri     = data.get("verification_uri_complete") or data.get("verification_uri", "")
    expires_in     = data.get("expires_in", 300)
    poll_interval  = data.get("interval", 2)

    if not device_code:
        print(f"  Incomplete device code response: {data}")
        return False

    print(f"\n  Open: {verify_uri}")
    print(f"  Code: {user_code}\n")
    try:
        webbrowser.open(verify_uri)
    except Exception:
        pass

    # Step 2: poll for token
    deadline = time.time() + expires_in
    async with httpx.AsyncClient(timeout=15) as client:
        while time.time() < deadline:
            await asyncio.sleep(poll_interval)
            r = await client.post(
                cfg["token_url"],
                content=urlencode({
                    "grant_type":    cfg["grant_type"],
                    "client_id":     cfg["client_id"],
                    "device_code":   device_code,
                    "code_verifier": verifier,
                }).encode(),
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept":       "application/json",
                },
            )

            if r.is_success:
                payload = r.json()
                if payload.get("access_token"):
                    token = {
                        "access":  payload["access_token"],
                        "refresh": payload.get("refresh_token", ""),
                        "expires": int(time.time() * 1000) + payload.get("expires_in", 3600) * 1000,
                    }
                    if payload.get("resource_url"):
                        token["resource_url"] = payload["resource_url"]
                    save_token(provider, token)
                    return True

            try:
                err = r.json().get("error", "")
            except Exception:
                err = ""

            if err == "slow_down":
                poll_interval = min(poll_interval * 1.5, 10)
            elif err not in ("authorization_pending", ""):
                print(f"  Auth error: {err}")
                return False

            print("  Waiting for approval…", end="\r")

    print("\n  Timed out.")
    return False
