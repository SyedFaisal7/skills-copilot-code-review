"""
Announcement endpoints for the High School Management System API.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Cookie, HTTPException
from pydantic import BaseModel, Field

from ..database import announcements_collection
from .auth import SESSION_COOKIE_NAME, get_authenticated_teacher

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"],
)


class AnnouncementPayload(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    start_date: Optional[str] = None
    expiration_date: str = Field(min_length=1)


def _coerce_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Dates must use YYYY-MM-DD format") from exc


def _serialize_announcement(announcement: Dict[str, Any]) -> Dict[str, Any]:
    announcement = dict(announcement)
    announcement["id"] = str(announcement.pop("_id"))
    return announcement


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def list_announcements() -> List[Dict[str, Any]]:
    """Return all announcements sorted by expiration date."""
    announcements = list(announcements_collection.find({}))
    announcements.sort(key=lambda item: item.get("expiration_date", ""))
    return [_serialize_announcement(item) for item in announcements]


@router.post("", status_code=201)
def create_announcement(
    payload: AnnouncementPayload,
    session_token: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
) -> Dict[str, Any]:
    """Create a new announcement. Requires a signed-in teacher account."""
    get_authenticated_teacher(session_token)

    start_date = _coerce_date(payload.start_date)
    expiration_date = _coerce_date(payload.expiration_date)
    if expiration_date is None:
        raise HTTPException(status_code=400, detail="Expiration date is required")
    if start_date and expiration_date < start_date:
        raise HTTPException(status_code=400, detail="Expiration date cannot be before the start date")

    announcement_id = str(uuid4())
    announcements_collection.insert_one(
        {
            "_id": announcement_id,
            "message": payload.message.strip(),
            "start_date": payload.start_date,
            "expiration_date": payload.expiration_date,
            "created_at": datetime.utcnow().isoformat(),
        }
    )

    announcement = announcements_collection.find_one({"_id": announcement_id})
    return _serialize_announcement(announcement)


@router.put("/{announcement_id}")
def update_announcement(
    announcement_id: str,
    payload: AnnouncementPayload,
    session_token: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
) -> Dict[str, Any]:
    """Update an announcement. Requires a signed-in teacher account."""
    get_authenticated_teacher(session_token)

    start_date = _coerce_date(payload.start_date)
    expiration_date = _coerce_date(payload.expiration_date)
    if expiration_date is None:
        raise HTTPException(status_code=400, detail="Expiration date is required")
    if start_date and expiration_date < start_date:
        raise HTTPException(status_code=400, detail="Expiration date cannot be before the start date")

    result = announcements_collection.update_one(
        {"_id": announcement_id},
        {
            "$set": {
                "message": payload.message.strip(),
                "start_date": payload.start_date,
                "expiration_date": payload.expiration_date,
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    announcement = announcements_collection.find_one({"_id": announcement_id})
    return _serialize_announcement(announcement)


@router.delete("/{announcement_id}")
def delete_announcement(
    announcement_id: str,
    session_token: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
) -> Dict[str, Any]:
    """Delete an announcement. Requires a signed-in teacher account."""
    get_authenticated_teacher(session_token)

    result = announcements_collection.delete_one({"_id": announcement_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted"}
