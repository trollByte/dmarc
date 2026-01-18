"""
Saved View API Routes

Endpoints for managing saved dashboard views.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.saved_view_service import SavedViewService
from app.schemas.saved_view_schemas import (
    SavedViewCreate,
    SavedViewUpdate,
    SavedViewResponse,
    SavedViewListResponse
)

router = APIRouter(prefix="/saved-views", tags=["Saved Views"])


@router.get("", response_model=SavedViewListResponse)
async def list_saved_views(
    include_shared: bool = Query(True, description="Include shared views from other users"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all saved views accessible to the current user.

    Returns user's own views and optionally shared views from other users.
    """
    views, total = SavedViewService.get_user_views(
        db,
        user_id=current_user.id,
        include_shared=include_shared
    )

    # Add username for response
    response_views = []
    for view in views:
        view_dict = {
            "id": view.id,
            "name": view.name,
            "description": view.description,
            "icon": view.icon,
            "filters": view.filters,
            "display_settings": view.display_settings,
            "is_shared": view.is_shared,
            "is_default": view.is_default,
            "created_at": view.created_at,
            "updated_at": view.updated_at,
            "last_used_at": view.last_used_at,
            "user_id": view.user_id,
            "username": view.user.username if view.user else None
        }
        response_views.append(SavedViewResponse(**view_dict))

    return SavedViewListResponse(views=response_views, total=total)


@router.get("/default", response_model=Optional[SavedViewResponse])
async def get_default_view(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the user's default view, if set."""
    view = SavedViewService.get_default_view(db, current_user.id)
    if not view:
        return None
    return view


@router.get("/{view_id}", response_model=SavedViewResponse)
async def get_saved_view(
    view_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific saved view by ID."""
    view = SavedViewService.get_view_by_id(db, view_id, current_user.id)
    if not view:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved view not found"
        )
    return view


@router.post("", response_model=SavedViewResponse, status_code=status.HTTP_201_CREATED)
async def create_saved_view(
    data: SavedViewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new saved view."""
    view = SavedViewService.create_view(
        db,
        user_id=current_user.id,
        name=data.name,
        description=data.description,
        icon=data.icon,
        filters=data.filters,
        display_settings=data.display_settings,
        is_shared=data.is_shared,
        is_default=data.is_default
    )
    return view


@router.patch("/{view_id}", response_model=SavedViewResponse)
async def update_saved_view(
    view_id: UUID,
    data: SavedViewUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a saved view.

    Only the owner can update a view.
    """
    view = SavedViewService.update_view(
        db,
        view_id=view_id,
        user_id=current_user.id,
        **data.model_dump(exclude_unset=True)
    )
    if not view:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved view not found or you don't have permission to update it"
        )
    return view


@router.delete("/{view_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_view(
    view_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a saved view.

    Only the owner can delete a view.
    """
    success = SavedViewService.delete_view(db, view_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved view not found or you don't have permission to delete it"
        )
    return None


@router.post("/{view_id}/use", response_model=SavedViewResponse)
async def use_saved_view(
    view_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mark a saved view as used (updates last_used_at).

    Called when a user applies a saved view.
    """
    view = SavedViewService.mark_as_used(db, view_id, current_user.id)
    if not view:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved view not found"
        )
    return view


@router.post("/{view_id}/set-default", response_model=SavedViewResponse)
async def set_default_view(
    view_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Set a view as the user's default.

    Only works for views owned by the user.
    """
    view = SavedViewService.set_default_view(db, view_id, current_user.id)
    if not view:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved view not found or you don't own this view"
        )
    return view


@router.post("/{view_id}/duplicate", response_model=SavedViewResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_saved_view(
    view_id: UUID,
    name: Optional[str] = Query(None, description="Name for the duplicated view"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Duplicate a saved view.

    Can duplicate own views or shared views from other users.
    """
    view = SavedViewService.duplicate_view(
        db,
        view_id=view_id,
        user_id=current_user.id,
        new_name=name
    )
    if not view:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved view not found"
        )
    return view
