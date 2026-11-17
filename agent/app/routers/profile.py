from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import db
from app.auth import CurrentUser, get_current_user, mint_dev_token
from app.config import get_settings
from app.generate.schemas import ProfileUpdate

router = APIRouter(tags=["profile"])


def _ensure_profile(user: CurrentUser) -> dict:
    db.execute("insert into profiles (id) values (%s) on conflict (id) do nothing", (user.id,))
    return db.fetch_one("select * from profiles where id = %s", (user.id,))


@router.get("/me")
def get_me(user: CurrentUser = Depends(get_current_user)):
    profile = _ensure_profile(user)
    stats = db.fetch_one(
        "select (select count(*) from textbooks where user_id = %(u)s) as textbooks,"
        " (select count(*) from papers where user_id = %(u)s) as papers,"
        " (select count(*) from questions where user_id = %(u)s) as questions",
        {"u": user.id},
    )
    onboarded = bool(profile.get("name") and profile.get("board"))
    return {**profile, "email": user.email, "onboarded": onboarded, "stats": stats}


@router.put("/me")
def update_me(body: ProfileUpdate, user: CurrentUser = Depends(get_current_user)):
    _ensure_profile(user)
    changes = body.model_dump(exclude_unset=True)
    if changes:
        cols = ", ".join(f"{k} = %({k})s" for k in changes)
        db.execute(f"update profiles set {cols} where id = %(id)s", {**changes, "id": user.id})
    return get_me(user)


# --------------------------------------------------------------- dev login
class DevLogin(BaseModel):
    email: str = Field(min_length=3, max_length=200, pattern=r"^[^@\s]+@[^@\s]+$")


@router.post("/dev/token", tags=["dev"], include_in_schema=False)
def dev_token(body: DevLogin):
    """LOCAL TESTING ONLY (DEV_AUTH=true): log in as any email without Supabase Auth."""
    if not get_settings().dev_auth:
        raise HTTPException(404, "Not found")
    user_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"slaybus-dev:{body.email.lower()}"))
    db.execute("insert into auth.users (id) values (%s) on conflict (id) do nothing", (user_id,))
    return {"access_token": mint_dev_token(user_id, body.email.lower()), "user_id": user_id, "email": body.email.lower()}
