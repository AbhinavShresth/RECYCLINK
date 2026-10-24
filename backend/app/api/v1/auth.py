from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_current_user, require_csrf
from app.core.config import get_settings
from app.core.rate_limit import rate_limit
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    create_csrf_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.identity import User, UserProfile, UserRole
from app.schemas.identity import LoginIn, ProfilePatch, RegistrationIn, UserPublic

router = APIRouter(prefix="/auth", tags=["authentication"])
settings = get_settings()


def roles_for(user: User) -> list[str]:
    return sorted({link.role_code for link in user.roles})


def public_user(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        email=user.email,
        full_name=user.profile.full_name,
        preferred_language=user.profile.preferred_language,
        roles=roles_for(user),
        created_at=user.created_at,
    )


def set_session_cookies(response: Response, user: User) -> None:
    csrf = create_csrf_token()
    secure = settings.app_env.lower() == "production"
    response.set_cookie("recyclink_session", create_access_token(user.id), httponly=True, secure=secure, samesite="lax", max_age=4 * 60 * 60, path="/")
    response.set_cookie("csrf_token", csrf, httponly=False, secure=secure, samesite="strict", max_age=4 * 60 * 60, path="/")


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(payload: RegistrationIn, response: Response, db: Session = Depends(get_db)) -> UserPublic:
    if db.scalar(select(User.id).where(User.email == payload.email)):
        raise HTTPException(status_code=409, detail="Email is already registered")
    user = User(email=payload.email, password_hash=hash_password(payload.password))
    user.profile = UserProfile(full_name=payload.full_name, preferred_language=payload.preferred_language)
    user.roles = [UserRole(role_code="USER")]
    if payload.enable_recycler:
        user.roles.append(UserRole(role_code="RECYCLER"))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email is already registered") from None
    db.refresh(user)
    user = db.scalar(select(User).options(selectinload(User.roles)).where(User.id == user.id))
    set_session_cookies(response, user)
    return public_user(user)


@router.post("/login", response_model=UserPublic, dependencies=[Depends(rate_limit("auth-login", 12, 60))])
def login(payload: LoginIn, response: Response, db: Session = Depends(get_db)) -> UserPublic:
    user = db.scalar(select(User).options(selectinload(User.roles), selectinload(User.profile)).where(User.email == payload.email))
    hashed = user.password_hash if user else DUMMY_PASSWORD_HASH
    verified = verify_password(payload.password, hashed)
    if user is None or not verified or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email or password is incorrect")
    set_session_cookies(response, user)
    return public_user(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, _: None = Depends(require_csrf)) -> Response:
    response.delete_cookie("recyclink_session", path="/", samesite="lax")
    response.delete_cookie("csrf_token", path="/", samesite="strict")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user)) -> UserPublic:
    return public_user(user)


@router.patch("/me", response_model=UserPublic, dependencies=[Depends(require_csrf)])
def update_profile(payload: ProfilePatch, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> UserPublic:
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(user.profile, key, " ".join(value.split()) if key == "full_name" else value)
    db.commit()
    db.refresh(user.profile)
    return public_user(user)
