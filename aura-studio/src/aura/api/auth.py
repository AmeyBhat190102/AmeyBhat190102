"""Engine-side auth: the web app (Auth.js) mints a short-lived HS256 JWT
(sub=user_id, tier) with the shared secret; we verify it here — no auth
database reads in the engine hot path. Anonymous access is allowed where the
product wants it (preview-tier projects) — routes decide."""

from __future__ import annotations

from dataclasses import dataclass

import jwt
from fastapi import Header, HTTPException


@dataclass
class Caller:
    user_id: str | None
    tier: str = "preview"
    is_editor: bool = False


def make_verifier(secret: str):
    async def verify(authorization: str | None = Header(default=None)) -> Caller:
        if not authorization or not authorization.startswith("Bearer "):
            return Caller(user_id=None)
        try:
            claims = jwt.decode(authorization.removeprefix("Bearer "), secret,
                                algorithms=["HS256"])
        except jwt.PyJWTError as e:
            raise HTTPException(401, f"invalid token: {e}")
        return Caller(user_id=claims.get("sub"), tier=claims.get("tier", "preview"),
                      is_editor=bool(claims.get("editor")))

    return verify
