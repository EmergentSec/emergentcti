import uuid

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from cti.models.saved_search import SavedSearch
from cti.schemas.saved_search import SavedSearchCreate, SavedSearchUpdate

MAX_SAVED_SEARCHES_PER_USER = 50


async def list_saved_searches(
    db: AsyncSession, user_id: uuid.UUID
) -> list[SavedSearch]:
    """Return user's own searches + shared searches from others.

    Order by is_default desc, name asc. Limit 50 total.
    """
    result = await db.execute(
        select(SavedSearch)
        .options(joinedload(SavedSearch.user))
        .where(
            or_(
                SavedSearch.user_id == user_id,
                SavedSearch.is_shared.is_(True),
            )
        )
        .order_by(SavedSearch.is_default.desc(), SavedSearch.name.asc())
        .limit(MAX_SAVED_SEARCHES_PER_USER)
    )
    return list(result.scalars().unique().all())


async def create_saved_search(
    db: AsyncSession, user_id: uuid.UUID, data: SavedSearchCreate
) -> SavedSearch:
    """Create a saved search. Check user hasn't exceeded 50 saved searches."""
    count_result = await db.execute(
        select(SavedSearch.id).where(SavedSearch.user_id == user_id)
    )
    count = len(count_result.all())
    if count >= MAX_SAVED_SEARCHES_PER_USER:
        raise ValueError(
            f"Maximum of {MAX_SAVED_SEARCHES_PER_USER} saved searches per user"
        )

    saved_search = SavedSearch(
        name=data.name,
        user_id=user_id,
        filters=data.filters.model_dump(exclude_none=True),
        is_shared=data.is_shared,
    )
    db.add(saved_search)
    await db.flush()
    await db.refresh(saved_search, ["user"])
    return saved_search


async def update_saved_search(
    db: AsyncSession,
    search_id: uuid.UUID,
    user_id: uuid.UUID,
    data: SavedSearchUpdate,
) -> SavedSearch | None:
    """Update a saved search. Only the owner can update."""
    result = await db.execute(
        select(SavedSearch)
        .options(joinedload(SavedSearch.user))
        .where(SavedSearch.id == search_id)
    )
    saved_search = result.scalar_one_or_none()
    if not saved_search:
        return None
    if saved_search.user_id != user_id:
        return None

    update_data = data.model_dump(exclude_unset=True)
    if "filters" in update_data and update_data["filters"] is not None:
        update_data["filters"] = data.filters.model_dump(exclude_none=True)

    for field, value in update_data.items():
        setattr(saved_search, field, value)

    await db.flush()
    await db.refresh(saved_search, ["user"])
    return saved_search


async def delete_saved_search(
    db: AsyncSession, search_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    """Delete a saved search. Only the owner can delete."""
    result = await db.execute(
        select(SavedSearch).where(SavedSearch.id == search_id)
    )
    saved_search = result.scalar_one_or_none()
    if not saved_search:
        return False
    if saved_search.user_id != user_id:
        return False
    await db.delete(saved_search)
    await db.flush()
    return True


async def set_default_search(
    db: AsyncSession, search_id: uuid.UUID, user_id: uuid.UUID
) -> SavedSearch | None:
    """Set a saved search as default, unsetting any other defaults for this user."""
    result = await db.execute(
        select(SavedSearch)
        .options(joinedload(SavedSearch.user))
        .where(SavedSearch.id == search_id)
    )
    saved_search = result.scalar_one_or_none()
    if not saved_search:
        return None

    # User must own the search or it must be shared
    if saved_search.user_id != user_id and not saved_search.is_shared:
        return None

    # Unset any existing defaults for this user
    await db.execute(
        update(SavedSearch)
        .where(SavedSearch.user_id == user_id, SavedSearch.is_default.is_(True))
        .values(is_default=False)
    )

    # Set the new default
    saved_search.is_default = True
    await db.flush()
    await db.refresh(saved_search, ["user"])
    return saved_search
