from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from stockguard.database import get_db
from stockguard.models.user import User
from stockguard.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    RevokeTokenRequest,
    UserResponse,
)
from stockguard.services.auth_service import (
    AuthService,
    AuthenticationException,
    UserAlreadyExistsException,
    InvalidTokenException,
)
from stockguard.security.deps import get_current_user
from stockguard.security.rate_limiter import limit_auth_request

router = APIRouter(prefix="/auth", tags=["Authentication & RBAC"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit_auth_request)],
)
def register(req: UserRegisterRequest, db: Session = Depends(get_db)):
    try:
        user = AuthService.register_user(db, req)
        return user
    except UserAlreadyExistsException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(limit_auth_request)],
)
def login(req: UserLoginRequest, db: Session = Depends(get_db)):
    try:
        user = AuthService.authenticate_user(db, req.email, req.password)
        return AuthService.issue_tokens(db, user)
    except AuthenticationException as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(limit_auth_request)],
)
def refresh_token(req: RefreshTokenRequest, db: Session = Depends(get_db)):
    try:
        return AuthService.rotate_refresh_token(db, req.refresh_token)
    except (InvalidTokenException, AuthenticationException) as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/revoke", status_code=status.HTTP_200_OK)
def revoke_token(req: RevokeTokenRequest, db: Session = Depends(get_db)):
    revoked = AuthService.revoke_refresh_token(db, req.refresh_token)
    return {"status": "ok", "revoked": revoked}


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    return current_user
