"""
Saved View Service

Business logic for managing saved dashboard views.
"""

from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import or_, and_
from sqlalchemy.orm import Session

from app.models.saved_view import SavedView
from app.models.user import User


class SavedViewService:
    """Service for managing saved views"""

    @staticmethod
    def create_view(
        db: Session,
        user_id: UUID,
        name: str,
        filters: dict,
        description: Optional[str] = None,
        icon: Optional[str] = None,
        display_settings: Optional[dict] = None,
        is_shared: bool = False,
        is_default: bool = False
    ) -> SavedView:
        """Create a new saved view"""
        # If setting as default, unset other defaults for this user
        if is_default:
            db.query(SavedView).filter(
                and_(
                    SavedView.user_id == user_id,
                    SavedView.is_default == True
                )
            ).update({SavedView.is_default: False})

        view = SavedView(
            user_id=user_id,
            name=name,
            description=description,
            icon=icon,
            filters=filters,
            display_settings=display_settings or {},
            is_shared=is_shared,
            is_default=is_default
        )
        db.add(view)
        db.commit()
        db.refresh(view)
        return view

    @staticmethod
    def get_user_views(
        db: Session,
        user_id: UUID,
        include_shared: bool = True
    ) -> Tuple[List[SavedView], int]:
        """
        Get all views accessible to a user.

        Returns own views + shared views from other users.
        """
        if include_shared:
            query = db.query(SavedView).filter(
                or_(
                    SavedView.user_id == user_id,
                    SavedView.is_shared == True
                )
            )
        else:
            query = db.query(SavedView).filter(SavedView.user_id == user_id)

        views = query.order_by(
            SavedView.is_default.desc(),
            SavedView.last_used_at.desc().nullslast(),
            SavedView.created_at.desc()
        ).all()

        return views, len(views)

    @staticmethod
    def get_view_by_id(
        db: Session,
        view_id: UUID,
        user_id: UUID
    ) -> Optional[SavedView]:
        """
        Get a specific view by ID.

        Returns the view if owned by user or if shared.
        """
        return db.query(SavedView).filter(
            and_(
                SavedView.id == view_id,
                or_(
                    SavedView.user_id == user_id,
                    SavedView.is_shared == True
                )
            )
        ).first()

    @staticmethod
    def update_view(
        db: Session,
        view_id: UUID,
        user_id: UUID,
        **kwargs
    ) -> Optional[SavedView]:
        """
        Update a saved view.

        Only the owner can update a view.
        """
        view = db.query(SavedView).filter(
            and_(
                SavedView.id == view_id,
                SavedView.user_id == user_id
            )
        ).first()

        if not view:
            return None

        # Handle setting as default
        if kwargs.get('is_default', False):
            db.query(SavedView).filter(
                and_(
                    SavedView.user_id == user_id,
                    SavedView.is_default == True,
                    SavedView.id != view_id
                )
            ).update({SavedView.is_default: False})

        # Update fields
        for key, value in kwargs.items():
            if value is not None and hasattr(view, key):
                setattr(view, key, value)

        view.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(view)
        return view

    @staticmethod
    def delete_view(
        db: Session,
        view_id: UUID,
        user_id: UUID
    ) -> bool:
        """
        Delete a saved view.

        Only the owner can delete a view.
        """
        view = db.query(SavedView).filter(
            and_(
                SavedView.id == view_id,
                SavedView.user_id == user_id
            )
        ).first()

        if not view:
            return False

        db.delete(view)
        db.commit()
        return True

    @staticmethod
    def mark_as_used(
        db: Session,
        view_id: UUID,
        user_id: UUID
    ) -> Optional[SavedView]:
        """Update the last_used_at timestamp when a view is applied"""
        view = SavedViewService.get_view_by_id(db, view_id, user_id)
        if view:
            view.update_last_used()
            db.commit()
            db.refresh(view)
        return view

    @staticmethod
    def set_default_view(
        db: Session,
        view_id: UUID,
        user_id: UUID
    ) -> Optional[SavedView]:
        """Set a view as the user's default"""
        # First, unset all defaults for this user
        db.query(SavedView).filter(
            and_(
                SavedView.user_id == user_id,
                SavedView.is_default == True
            )
        ).update({SavedView.is_default: False})

        # Set the specified view as default
        view = db.query(SavedView).filter(
            and_(
                SavedView.id == view_id,
                SavedView.user_id == user_id
            )
        ).first()

        if view:
            view.is_default = True
            db.commit()
            db.refresh(view)

        return view

    @staticmethod
    def get_default_view(
        db: Session,
        user_id: UUID
    ) -> Optional[SavedView]:
        """Get the user's default view"""
        return db.query(SavedView).filter(
            and_(
                SavedView.user_id == user_id,
                SavedView.is_default == True
            )
        ).first()

    @staticmethod
    def get_shared_views(db: Session) -> List[SavedView]:
        """Get all shared views (for admin/analytics)"""
        return db.query(SavedView).filter(
            SavedView.is_shared == True
        ).order_by(SavedView.created_at.desc()).all()

    @staticmethod
    def duplicate_view(
        db: Session,
        view_id: UUID,
        user_id: UUID,
        new_name: Optional[str] = None
    ) -> Optional[SavedView]:
        """
        Duplicate a view.

        Can duplicate own views or shared views.
        """
        original = SavedViewService.get_view_by_id(db, view_id, user_id)
        if not original:
            return None

        new_view = SavedView(
            user_id=user_id,
            name=new_name or f"{original.name} (Copy)",
            description=original.description,
            icon=original.icon,
            filters=original.filters.copy() if original.filters else {},
            display_settings=original.display_settings.copy() if original.display_settings else {},
            is_shared=False,
            is_default=False
        )
        db.add(new_view)
        db.commit()
        db.refresh(new_view)
        return new_view
