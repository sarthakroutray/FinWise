from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import firebase_admin
from fastapi import Depends, Header, HTTPException
from firebase_admin import auth, credentials

from app.core.config import config


@dataclass
class AuthUser:
    """Represents an authenticated Firebase user."""

    uid: str
    email: str | None


def _initialize_firebase() -> None:
    """Initialize Firebase Admin SDK once using configured credentials."""
    if firebase_admin._apps:
        return

    cred_obj = None
    if config.FIREBASE_CREDENTIALS_JSON:
        try:
            cred_info = json.loads(config.FIREBASE_CREDENTIALS_JSON)
            cred_obj = credentials.Certificate(cred_info)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Invalid FIREBASE_CREDENTIALS_JSON: {exc}") from exc
    elif config.FIREBASE_CREDENTIALS_PATH:
        path = Path(config.FIREBASE_CREDENTIALS_PATH)
        if not path.exists():
            raise RuntimeError(f"FIREBASE_CREDENTIALS_PATH not found: {path}")
        cred_obj = credentials.Certificate(str(path))

    if cred_obj is None:
        raise RuntimeError(
            "Firebase is not configured. Set FIREBASE_CREDENTIALS_PATH or FIREBASE_CREDENTIALS_JSON."
        )

    firebase_admin.initialize_app(cred_obj)


def verify_bearer_token(authorization: str | None = Header(default=None)) -> AuthUser:
    """Verify Firebase ID token from Authorization header and return user info."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    try:
        _initialize_firebase()
        decoded = auth.verify_id_token(token)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail=f"Token verification failed: {exc}") from exc

    uid = str(decoded.get("uid", "")).strip()
    if not uid:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    email = decoded.get("email")
    return AuthUser(uid=uid, email=str(email) if email else None)


def get_current_user(user: AuthUser = Depends(verify_bearer_token)) -> AuthUser:
    """FastAPI dependency wrapper for Firebase-authenticated user."""
    return user
