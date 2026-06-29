"""
Authentication endpoints for the High School Management System API
"""

from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe
from typing import Any, Dict, Optional

from fastapi import APIRouter, Cookie, HTTPException, Response

from ..database import teachers_collection, verify_password

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

SESSION_COOKIE_NAME = "teacher_session"
SESSION_DURATION = timedelta(hours=12)
teacher_sessions: Dict[str, Dict[str, Any]] = {}


def _create_teacher_session(username: str) -> str:
    session_token = token_urlsafe(32)
    teacher_sessions[session_token] = {
        "username": username,
        "expires_at": datetime.now(timezone.utc) + SESSION_DURATION,
    }
    return session_token


def get_authenticated_teacher(session_token: Optional[str]) -> Dict[str, Any]:
    """Return the teacher associated with a valid session token."""
    if not session_token:
        raise HTTPException(status_code=401, detail="Authentication required for this action")

    session = teacher_sessions.get(session_token)
    if not session or session["expires_at"] <= datetime.now(timezone.utc):
        teacher_sessions.pop(session_token, None)
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")

    teacher = teachers_collection.find_one({"_id": session["username"]})
    if not teacher:
        teacher_sessions.pop(session_token, None)
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")

    return teacher


@router.post("/login")
def login(username: str, password: str, response: Response) -> Dict[str, Any]:
    """Login a teacher account"""
    # Find the teacher in the database
    teacher = teachers_collection.find_one({"_id": username})

    # Verify password using Argon2 verifier from database.py
    if not teacher or not verify_password(teacher.get("password", ""), password):
        raise HTTPException(
            status_code=401, detail="Invalid username or password")

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=_create_teacher_session(teacher["username"]),
        httponly=True,
        samesite="lax",
        max_age=int(SESSION_DURATION.total_seconds()),
    )

    # Return teacher information (excluding password)
    return {
        "username": teacher["username"],
        "display_name": teacher["display_name"],
        "role": teacher["role"]
    }


@router.get("/check-session")
def check_session(
    session_token: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME)
) -> Dict[str, Any]:
    """Check whether the current authenticated session is valid."""
    teacher = get_authenticated_teacher(session_token)

    return {
        "username": teacher["username"],
        "display_name": teacher["display_name"],
        "role": teacher["role"]
    }


@router.post("/logout")
def logout(
    response: Response,
    session_token: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
) -> Dict[str, Any]:
    """Log out the current teacher session."""
    if session_token:
        teacher_sessions.pop(session_token, None)

    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"message": "Logged out"}
