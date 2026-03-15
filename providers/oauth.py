"""
providers/oauth.py — Device-code OAuth flow for providers that support it.
Currently: Qwen (qwen-portal), extensible for others.

Token storage: ~/.sonder/tokens/{provider}.json
"""
import asyncio
import json
import time
import webbrowser
from pathlib import Path

import httpx

TOKEN_DIR = Path.home() / ".sonder" / "tokens"
TOKEN_DIR.mkdir(parents=True, exist_ok=True)

# ── Provider OAuth configs ────────────────────────────────────────────────────

OAUTH_PROVIDERS: dict[str, dict] = {
    "qwen-portal": {
        "display_name": "Qwen",
        "device_auth_url": "https://chat.qwen.ai/api/v1/oauth/device/code",
        "token_url":       "https://chat.qwen.ai/api/v1/oauth/token",
        "base_url":        "https://portal.qwen.ai/v1",
        "client_id":       "qwen-code",
        "default_model":   "qwen-portal/coder-model",
        "poll_interval":   3,
    },
}


# ── Token storage ─────────────────────────────────────────────────────────────

def _token_path(provider: str) -> Path:
    return TOKEN_DIR / f"{provider}.json"


def load_token(provider: str) -> dict | None:
    p = _token_path(provider)
    if not p.exists():
        return None
    return json.loads(p.read_text())


def save_token(provider: str, token: dict):
    _token_path(provider).write_text(json.dumps(token, indent=2))


def get_access_token(provider: str) -> str | None:
    """Return a valid access token, refreshing if needed."""
    token = load_token(provider)
    if not token:
        return None
    # Check expiry (with 60s buffer)
    if token.get("expires_at", 0) > time.time() + 60:
        return token["access_token"]
    # Try refresh
    refreshed = _sync_refresh(provider, token.get("refresh_token", ""))
    if refreshed:
        return refreshed
    return None


def _sync_refresh(provider: str, refresh_token: str) -> str | None:
    cfg = OAUTH_PROVIDERS.get(provider)
    if not cfg or not refresh_token:
        return None
    try:
        r = httpx.post(cfg["token_url"], json={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": cfg["client_id"],
        }, timeout=10)
        data = r.json()
        if "access_token" in data:
            data["expires_at"] = time.time() + data.get("expires_in", 3600)
            save_token(provider, data)
            return data["access_token"]
    except Exception:
        pass
    return None


# ── Device-code login flow ────────────────────────────────────────────────────

async def login(provider: str) -> bool:
    """
    Run device-code OAuth flow for the given provider.
    Prints instructions, polls for token, saves on success.
    Returns True on success.
    """
    cfg = OAUTH_PROVIDERS.get(provider)
    if not cfg:
        print(f"OAuth not supported for {provider}")
        return False

    async with httpx.AsyncClient(timeout=15) as client:
        # Step 1: request device code
        r = await client.post(cfg["device_auth_url"], json={"client_id": cfg["client_id"]})
        data = r.json()

    device_code  = data.get("device_code", "")
    user_code    = data.get("user_code", "")
    verify_url   = data.get("verification_uri") or data.get("verification_url", "")
    expires_in   = data.get("expires_in", 300)
    interval     = data.get("interval", cfg["poll_interval"])

    if not device_code:
        print(f"Failed to get device code: {data}")
        return False

    full_url = f"{verify_url}?user_code={user_code}&client={cfg['client_id']}"
    print(f"\n  Open {full_url}")
    print(f"  If prompted, enter code: {user_code}\n")
    webbrowser.open(full_url)

    # Step 2: poll for token
    deadline = time.time() + expires_in
    async with httpx.AsyncClient(timeout=15) as client:
        while time.time() < deadline:
            await asyncio.sleep(interval)
            r = await client.post(cfg["token_url"], json={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_code,
                "client_id": cfg["client_id"],
            })
            token = r.json()
            if "access_token" in token:
                token["expires_at"] = time.time() + token.get("expires_in", 3600)
                save_token(provider, token)
                print(f"  ✓ {cfg['display_name']} OAuth complete")
                return True
            err = token.get("error", "")
            if err == "authorization_pending":
                print("  Waiting for approval…", end="\r")
                continue
            if err in ("expired_token", "access_denied"):
                print(f"  Auth failed: {err}")
                return False

    print("  Timed out waiting for approval.")
    return False
