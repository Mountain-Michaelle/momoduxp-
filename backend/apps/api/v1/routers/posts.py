"""
Posts API router for FastAPI.
Handles CRUD operations for scheduled posts and Celery task integration.
"""

from typing import Optional
from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from shared.database import get_db
from shared.schemas import PaginatedResponse
from shared.schemas.posts import (
    PostCreate,
    PostUpdate,
    PostResponse,
    PostStatus as PostStatusEnum,
)

from shared.models.users import User
from shared.models.posts import ScheduledPost
from apps.api.v1.auth.dependencies import get_current_active_user
from apps.api.v1.tasks.post_task import trigger_publish_post, trigger_send_for_approval


router = APIRouter(prefix="/posts", tags=["posts"])


# ---------------------------------------------------
# Health Check
# ---------------------------------------------------

@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "posts"}


# ---------------------------------------------------
# List Posts (Pagination)
# ---------------------------------------------------

@router.get("/list", response_model=PaginatedResponse)
async def list_posts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):

    offset = (page - 1) * page_size

    base_query = select(ScheduledPost).where(
        ScheduledPost.author_id == current_user.id,
        ScheduledPost.is_active.is_(True),
    )

    if status:
        base_query = base_query.where(ScheduledPost.status == status)

    total_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(total_query)
    total = total_result.scalar()

    query = (
        base_query.order_by(ScheduledPost.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )

    result = await db.execute(query)
    posts = result.scalars().all()

    return PaginatedResponse(
        items=[PostResponse.model_validate(p) for p in posts],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


# ---------------------------------------------------
# Get Single Post
# ---------------------------------------------------

@router.get("/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):

    result = await db.execute(
        select(ScheduledPost).where(
            ScheduledPost.id == post_id,
            ScheduledPost.author_id == current_user.id,
        )
    )

    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    return PostResponse.model_validate(post)


# ---------------------------------------------------
# Create Post
# ---------------------------------------------------

@router.post("/create", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    post_data: PostCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):

    def _naive_utc(dt: datetime) -> datetime:
        """Strip tzinfo so asyncpg can store into TIMESTAMP WITHOUT TIME ZONE."""
        if dt is None:
            return dt
        return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt

    post = ScheduledPost(
        author_id=current_user.id,
        account_id=post_data.account_id,
        content=post_data.content,
        media_urls=[str(url) for url in post_data.media_urls],
        status=PostStatusEnum.DRAFT.value,
        scheduled_for=_naive_utc(post_data.scheduled_for),
        approval_deadline=_naive_utc(post_data.approval_deadline),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    db.add(post)
    await db.commit()
    await db.refresh(post)

    if post.approval_deadline:
        trigger_send_for_approval(str(post.id))

    return PostResponse.model_validate(post)


# ---------------------------------------------------
# Update Post
# ---------------------------------------------------

@router.patch("/update/{post_id}", response_model=PostResponse)
async def update_post(
    post_id: uuid.UUID,
    post_update: PostUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):

    result = await db.execute(
        select(ScheduledPost).where(
            ScheduledPost.id == post_id,
            ScheduledPost.author_id == current_user.id,
        )
    )

    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if post_update.content is not None:
        post.content = post_update.content

    if post_update.media_urls is not None:
        post.media_urls = post_update.media_urls

    if post_update.scheduled_for is not None:
        post.scheduled_for = post_update.scheduled_for

    if post_update.approval_deadline is not None:
        post.approval_deadline = post_update.approval_deadline

    if post_update.status is not None:
        post.status = post_update.status.value

    post.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(post)

    return PostResponse.model_validate(post)


# ---------------------------------------------------
# Delete Post (Soft Delete)
# ---------------------------------------------------

@router.delete("/delete/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):

    result = await db.execute(
        select(ScheduledPost).where(
            ScheduledPost.id == post_id,
            ScheduledPost.author_id == current_user.id,
        )
    )

    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    post.is_active = False
    post.updated_at = datetime.utcnow()

    await db.commit()


# ---------------------------------------------------
# Submit for Approval
# ------------------------------------------------
@router.post("/{post_id}/submit", response_model=PostResponse)
async def submit_for_approval(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):

    result = await db.execute(
        select(ScheduledPost).where(
            ScheduledPost.id == post_id,
            ScheduledPost.author_id == current_user.id,
        )
    )

    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if post.status not in [
        PostStatusEnum.DRAFT.value,
        PostStatusEnum.SENT_FOR_APPROVAL.value,
    ]:
        raise HTTPException(
            status_code=400,
            detail="Only draft or previously submitted posts can be submitted",
        )

    post.status = PostStatusEnum.SENT_FOR_APPROVAL.value
    post.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(post)

    trigger_send_for_approval(str(post.id))

    return PostResponse.model_validate(post)


# ---------------------------------------------------
# Approve Post
# ---------------------------------------------------

@router.post("/{post_id}/approve", response_model=PostResponse)
async def approve_post(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):

    result = await db.execute(
        select(ScheduledPost).where(
            ScheduledPost.id == post_id,
            ScheduledPost.author_id == current_user.id,
        )
    )

    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if post.status != PostStatusEnum.SENT_FOR_APPROVAL.value:
        raise HTTPException(
            status_code=400,
            detail="Only posts sent for approval can be approved",
        )

    now = datetime.utcnow()

    post.status = PostStatusEnum.APPROVED.value
    post.approved_at = now
    post.updated_at = now

    await db.commit()
    await db.refresh(post)

    trigger_publish_post(str(post.id))

    return PostResponse.model_validate(post)
