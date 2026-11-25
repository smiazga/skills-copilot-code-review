"""
Endpoints for managing announcements in the High School Management System API
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional, List
from datetime import datetime
from bson import ObjectId

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """
    Get all currently active announcements.
    An announcement is active if:
    - Current time is after or equal to start_date (if provided)
    - Current time is before expiration_date
    """
    now = datetime.now().isoformat()

    query = {
        "expiration_date": {"$gt": now}
    }

    # If start_date is provided, it must be less than or equal to now
    # We use $or to handle both cases: announcements without start_date and those with start_date in the past
    announcements = []
    for ann in announcements_collection.find(query):
        ann["_id"] = str(ann.get("_id", ""))
        start_date = ann.get("start_date")

        # If no start_date, announcement is active immediately
        if not start_date:
            announcements.append(ann)
        # If start_date exists, check if it's in the past
        elif start_date <= now:
            announcements.append(ann)

    return announcements


@router.get("/admin/all")
def get_all_announcements(teacher_username: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    """
    Get all announcements (admin only - requires teacher authentication)
    """
    # Check teacher authentication
    if not teacher_username:
        raise HTTPException(
            status_code=401, detail="Authentication required for this action")

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Invalid teacher credentials")

    announcements = []
    for ann in announcements_collection.find():
        ann["_id"] = str(ann.get("_id", ""))
        announcements.append(ann)

    return announcements


@router.post("/admin/create")
def create_announcement(
    title: str = Query(...),
    message: str = Query(...),
    expiration_date: str = Query(...),
    start_date: Optional[str] = Query(None),
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """
    Create a new announcement (admin only - requires teacher authentication)
    """
    # Check teacher authentication
    if not teacher_username:
        raise HTTPException(
            status_code=401, detail="Authentication required for this action")

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Invalid teacher credentials")

    # Validate dates
    try:
        exp_dt = datetime.fromisoformat(expiration_date)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid expiration_date format")

    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid start_date format")

        if start_dt >= exp_dt:
            raise HTTPException(
                status_code=400, detail="start_date must be before expiration_date")

    # Create announcement
    announcement = {
        "title": title,
        "message": message,
        "start_date": start_date,
        "expiration_date": expiration_date,
        "created_at": datetime.now().isoformat(),
        "created_by": teacher_username
    }

    result = announcements_collection.insert_one(announcement)

    return {
        "_id": str(result.inserted_id),
        **announcement
    }


@router.put("/admin/{announcement_id}")
def update_announcement(
    announcement_id: str,
    title: Optional[str] = Query(None),
    message: Optional[str] = Query(None),
    expiration_date: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """
    Update an announcement (admin only - requires teacher authentication)
    """
    # Check teacher authentication
    if not teacher_username:
        raise HTTPException(
            status_code=401, detail="Authentication required for this action")

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Invalid teacher credentials")

    # Find announcement
    try:
        ann = announcements_collection.find_one(
            {"_id": ObjectId(announcement_id)})
    except Exception:
        raise HTTPException(status_code=404, detail="Announcement not found")

    if not ann:
        raise HTTPException(status_code=404, detail="Announcement not found")

    # Validate dates if provided
    update_data = {}

    if title is not None:
        update_data["title"] = title

    if message is not None:
        update_data["message"] = message

    if start_date is not None:
        try:
            datetime.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid start_date format")
        update_data["start_date"] = start_date

    if expiration_date is not None:
        try:
            datetime.fromisoformat(expiration_date)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid expiration_date format")
        update_data["expiration_date"] = expiration_date

    # Validate start_date < expiration_date
    final_start = update_data.get("start_date", ann.get("start_date"))
    final_exp = update_data.get("expiration_date", ann.get("expiration_date"))

    if final_start and final_exp and final_start >= final_exp:
        raise HTTPException(
            status_code=400, detail="start_date must be before expiration_date")

    result = announcements_collection.update_one(
        {"_id": ObjectId(announcement_id)},
        {"$set": update_data}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=500, detail="Failed to update announcement")

    # Return updated announcement
    updated = announcements_collection.find_one({"_id": ObjectId(announcement_id)})
    updated["_id"] = str(updated.get("_id", ""))
    return updated


@router.delete("/admin/{announcement_id}")
def delete_announcement(
    announcement_id: str,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """
    Delete an announcement (admin only - requires teacher authentication)
    """
    # Check teacher authentication
    if not teacher_username:
        raise HTTPException(
            status_code=401, detail="Authentication required for this action")

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Invalid teacher credentials")

    # Find and delete announcement
    try:
        result = announcements_collection.delete_one(
            {"_id": ObjectId(announcement_id)})
    except Exception:
        raise HTTPException(status_code=404, detail="Announcement not found")

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": f"Announcement {announcement_id} deleted successfully"}
