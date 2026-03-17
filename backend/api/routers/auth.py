# api/routes/auth.py

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.schemas import Token, LoginRequest, UserCreate, UserResponse
from shared.models import User
from api.services.auth import authenticate_user, issue_access_token, issue_tokens, register_user
from api.auth.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=Token)
async def login_form(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    user = await authenticate_user(db, form.username, form.password)
    return issue_tokens(user)


@router.post("/token", response_model=Token)
async def login_json(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    user = await authenticate_user(db, payload.username, payload.password)
    return issue_tokens(user)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    user = await register_user(
        db,
        username=payload.username,
        email=payload.email,
        password=payload.password,
        first_name=payload.first_name,
        last_name=payload.last_name,
    )
    
    return user


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/refresh", response_model=Token)
async def refresh(current_user: User = Depends(get_current_user)):
    return issue_access_token(current_user)
