"""
OAuth Repository - Data access layer for OAuth providers.
Handles OAuth accounts, token storage, and user linking.
"""

import uuid
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from shared.models.oauth import OAuthAccount
from shared.models.users import User
from apps.api.v1.repositories.user import get_user_by_email


logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# OAuth Provider Enum
# ─────────────────────────────────────────────────────────────


class OAuthProvider(str):
    GOOGLE = "google"
    GITHUB = "github"
    FACEBOOK = "facebook"


# ─────────────────────────────────────────────────────────────
# Repository Functions
# ─────────────────────────────────────────────────────────────


# class OAuthProvider(str):
#     GOOGLE = "google"
#     GITHUB = "github"
#     FACEBOOK = "facebook"


# ─────────────────────────────────────────────────────────────
# OAuth Account Model (for storing OAuth-linked accounts)
# ─────────────────────────────────────────────────────────────


# class OAuthAccount:
#     """
#     Represents a user's OAuth-linked account.
#     Stores provider info, tokens, and user association.
#     """

#     def __init__(
#         self,
#         id: uuid.UUID,
#         user_id: uuid.UUID,
#         provider: str,
#         provider_user_id: str,
#         access_token: str,
#         refresh_token: Optional[str],
#         id_token: Optional[str],
#         token_expires_at: Optional[datetime],
#         scope: str,
#         created_at: datetime,
#         updated_at: datetime,
#     ):
#         self.id = id
#         self.user_id = user_id
#         self.provider = provider
#         self.provider_user_id = provider_user_id
#         self.access_token = access_token
#         self.refresh_token = refresh_token
#         self.id_token = id_token
#         self.token_expires_at = token_expires_at
#         self.scope = scope
#         self.created_at = created_at
#         self.updated_at = updated_at


# ─────────────────────────────────────────────────────────────
# Repository Functions
# ─────────────────────────────────────────────────────────────


async def create_oauth_account(
    db: AsyncSession,
    user_id: str,
    provider: str,
    provider_user_id: str,
    access_token: str,
    refresh_token: Optional[str] = None,
    id_token: Optional[str] = None,
    token_expires_at: Optional[datetime] = None,
    scope: str = "",
) -> OAuthAccount:
    """
    Create a new OAuth account linked to a user.
    One user can have multiple OAuth providers (Google, GitHub, etc.)
    """
    # Check if OAuth account already exists for this provider
    existing = await get_oauth_account_by_provider_and_user(db, user_id, provider)
    if existing:
        logger.warning(
            "OAuth account already exists for user_id=%s provider=%s",
            user_id,
            provider,
        )
        # Update existing instead
        return await update_oauth_tokens(
            db,
            existing.id,
            access_token,
            refresh_token,
            id_token,
            token_expires_at,
            scope,
        )
    oauth_account = OAuthAccount(
        user_id=uuid.UUID(user_id),
        provider=provider,
        provider_user_id=provider_user_id,
        access_token=access_token,
        refresh_token=refresh_token,
        id_token=id_token,
        token_expires_at=token_expires_at,
        scope=scope,
    )
    db.add(oauth_account)
    await db.commit()
    await db.refresh(oauth_account)

    logger.info(
        "Created OAuth account: user_id=%s provider=%s provider_user_id=%s",
        user_id,
        provider,
        provider_user_id,
    )
    return oauth_account


async def get_oauth_account_by_provider_and_user(
    db: AsyncSession,
    user_id: str,
    provider: str,
) -> Optional[OAuthAccount]:

    stmt = select(OAuthAccount).where(
        OAuthAccount.user_id == uuid.UUID(user_id),
        OAuthAccount.provider == provider,
        OAuthAccount.is_active == True,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_oauth_account_by_provider_user_id(
    db: AsyncSession,
    provider: str,
    provider_user_id: str,
) -> Optional[OAuthAccount]:
    """Retrieve OAuth account by provider and provider's user ID."""
    stmt = select(OAuthAccount).where(
        OAuthAccount.provider == provider,
        OAuthAccount.provider_user_id == provider_user_id,
        OAuthAccount.is_active == True,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_oauth_tokens(
    db: AsyncSession,
    oauth_account_id: uuid.UUID,
    access_token: str,
    refresh_token: Optional[str],
    id_token: Optional[str],
    token_expires_at: Optional[datetime],
    scope: str,
) -> OAuthAccount:
    """
    Update OAuth account tokens after refresh or re-auth.
    """
    stmt = (
        update(OAuthAccount)
        .where(OAuthAccount.id == oauth_account_id)
        .values(
            access_token=access_token,
            refresh_token=refresh_token,
            id_token=id_token,
            token_expires_at=token_expires_at,
            scope=scope,
            updated_at=datetime.utcnow(),
        )
    )
    await db.execute(stmt)
    await db.commit()

    result = await db.get(OAuthAccount, oauth_account_id)
    logger.info("Updated OAuth tokens: oauth_account_id=%s", oauth_account_id)
    return result


async def delete_oauth_account(
    db: AsyncSession,
    oauth_account_id: uuid.UUID,
) -> bool:
    """
    Delete OAuth account (unlink OAuth provider).
    Used when user wants to disconnect their Google account.
    """
    stmt = (
        update(OAuthAccount)
        .where(OAuthAccount.id == oauth_account_id)
        .values(is_active=False, updated_at=datetime.utcnow())
    )

    await db.execute(stmt)
    await db.commit()
    logger.info("Deleted OAuth account: oauth_account_id=%s", oauth_account_id)
    return True


# ─────────────────────────────────────────────────────────────
# OAuth User Resolution
# ─────────────────────────────────────────────────────────────
async def get_user_oauth_accounts(
    db: AsyncSession,
    user_id: str,
) -> list[OAuthAccount]:
    """Get all OAuth accounts for a user."""
    stmt = select(OAuthAccount).where(
        OAuthAccount.user_id == uuid.UUID(user_id),
        OAuthAccount.is_active == True,
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# async def find_or_create_user_from_oauth(
#     db: AsyncSession,
#     provider: str,
#     provider_user_id: str,
#     email: str,
#     name: Optional[str] = None,
#     picture: Optional[str] = None,
# ) -> User:
#     """
#     Find existing user by OAuth account or create new user.
#     This is the core OAuth login flow - links OAuth to existing or new account.
#     """
#     # First, check if we have an OAuth account for this provider
#     oauth_account = await get_oauth_account_by_provider_user_id(
#         db, provider, provider_user_id
#     )

#     if oauth_account:
#         # User already exists - fetch and return
#         user = await db.get(User, oauth_account.user_id)
#         if user:
#             logger.info(
#                 "Found existing user from OAuth: user_id=%s provider=%s",
#                 user.id,
#                 provider,
#             )
#             return user
#         else:
#             logger.error(
#                 "OAuth account exists but user not found: user_id=%s",
#                 oauth_account.user_id,
#             )

#     # Check if user with this email already exists

#     existing_user = await get_user_by_email(db, email)
#     if existing_user:
#         # Link existing user to OAuth
#         logger.info(
#             "Linking existing user to OAuth: user_id=%s email=%s provider=%s",
#             existing_user.id,
#             email,
#             provider,
#         )
#         # Create OAuth account linking
#         await create_oauth_account(
#             db,
#             str(existing_user.id),
#             provider,
#             provider_user_id,
#             access_token="",  # Will be updated after token exchange
#         )
#         return existing_user

#     # Create new user from OAuth
#     logger.info(
#         "Creating new user from OAuth: email=%s provider=%s name=%s",
#         email,
#         provider,
#         name,
#     )

#     # Generate username from email or name
#     username = email.split("@")[0] if email else name or "user"

#     # Create user (would call user repository create function)
#     new_user = User(
#         id=uuid.uuid4(),
#         username=username,
#         email=email,
#         first_name=name.split()[0] if name else "",
#         last_name=" ".join(name.split()[1:]) if name and " " in name else "",
#         is_active=True,
#         is_superuser=False,
#     )

#     db.add(new_user)
#     await db.commit()
#     await db.refresh(new_user)

#     # Create OAuth account linking
#     await create_oauth_account(
#         db,
#         str(new_user.id),
#         provider,
#         provider_user_id,
#         access_token="",
#     )

#     return new_user
