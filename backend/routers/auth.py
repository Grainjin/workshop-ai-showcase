"""Auth API: register, login, social login, refresh, logout, current user, and account security."""

import secrets

from fastapi import Depends, File, HTTPException, Request, UploadFile
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from backend import models
from backend.auth import (
    create_password_identity,
    create_token_pair,
    ensure_user_can_login,
    find_user_by_email,
    get_current_user,
    get_db,
    get_now,
    get_password_identity,
    hash_password,
    normalize_email,
    revoke_refresh_token,
    revoke_user_refresh_tokens,
    validate_password_policy,
    validate_refresh_token,
    verify_password,
)
from backend.constants import DEMO_USER_EMAILS
from backend.schemas import (
    ApiResponse,
    AvatarUploadResponse,
    ChangeEmailRequest,
    ChangePasswordRequest,
    DemoLoginRequest,
    EmailCodeVerifyRequest,
    MockVerificationRequest,
    OAuthTokenResponse,
    RefreshTokenRequest,
    RegisterEmailCodeRequest,
    RegisterResponseData,
    SendEmailCodeRequest,
    SendEmailCodeResponse,
    SocialLoginRequest,
    SocialLoginResponseData,
    TokenResponse,
    UserProfilePatch,
    UserProfileUpdate,
    UserRegister,
    UserResponse,
)
from backend.services.email_verification_service import (
    EmailCodePurpose,
    consume_email_code,
    send_email_code,
)
from backend.services.social_auth_service import verify_social_identity
from backend.utils.demo_mode import (
    AccountEntryRoute,
    DemoModeRoute,
    reject_demo_restricted_action,
)
from backend.utils.formatters import format_user_response
from backend.utils.response import success_response
from backend.utils.router import ApiRouter
from backend.utils.upload import delete_local_upload, save_avatar_upload
from backend.utils.verification import (
    get_user_phone_number,
    mark_email_verified,
    mark_phone_verified,
)

router = ApiRouter(tags=["Auth"])
demo_router = ApiRouter(route_class=DemoModeRoute)
account_entry_router = ApiRouter(route_class=AccountEntryRoute)


def authenticate_user(email: str, password: str, db: Session):
    user = find_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    identity = get_password_identity(user, db)
    if not identity or not identity.password_hash:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(password, identity.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    ensure_user_can_login(user)
    return user


def login_user(user: models.User, db: Session):
    user.last_login_at = get_now()
    access_token, refresh_token = create_token_pair(user, db)
    db.commit()
    db.refresh(user)
    return access_token, refresh_token


def resolve_social_login_user(
    request_data: SocialLoginRequest,
    db: Session,
):
    if request_data.role == "admin":
        raise HTTPException(
            status_code=400,
            detail="Admin accounts cannot be created from social login",
        )

    verified_identity = verify_social_identity(
        request_data.provider.value,
        request_data.id_token,
        request_data.nonce,
    )

    social_account = (
        db.query(models.SocialAccount)
        .filter(
            models.SocialAccount.provider == verified_identity.provider,
            models.SocialAccount.provider_user_id == verified_identity.provider_user_id,
        )
        .first()
    )
    now = get_now()

    if social_account:
        user = db.query(models.User).filter(models.User.id == social_account.user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="Linked user does not exist")

        ensure_user_can_login(user)
        # Apple only sends the email on some sign-ins; keep the one on file.
        if verified_identity.email:
            social_account.provider_email = verified_identity.email
        social_account.provider_name = verified_identity.name or social_account.provider_name
        social_account.last_login_at = now
        return user, False, False

    # Only an address the provider verified may create or claim an account.
    # The app's own copy is never trusted: it would let anyone sign in to
    # an existing account by naming its email.
    email = normalize_email(verified_identity.email)
    if not email:
        raise HTTPException(
            status_code=400,
            detail="Social login did not provide a verified email address",
        )

    user = find_user_by_email(db, email)
    is_new_user = False

    if user:
        ensure_user_can_login(user)
        # Signing in with a provider that verified this address proves it.
        if user.email_verified_at is None:
            mark_email_verified(user)
    else:
        if not request_data.tos_accepted:
            raise HTTPException(
                status_code=409,
                detail="No account yet. Accept the Terms of Use to create one.",
            )

        first_name, last_name, display_name = _social_names(request_data, verified_identity, email)
        is_provider = request_data.role.value == "provider"
        user = models.User(
            name=display_name,
            first_name=first_name,
            last_name=last_name,
            tos_accepted_at=now,
            email=email,
            role=request_data.role.value,
            is_active=True,
            is_banned=False,
            last_login_at=None,
            email_verified_at=now,
            created_at=now,
            identity_verification_status="not_submitted" if is_provider else None,
            qualification_verification_status="not_submitted" if is_provider else None,
        )
        db.add(user)
        db.flush()
        is_new_user = True

    social_account = models.SocialAccount(
        user_id=user.id,
        provider=verified_identity.provider,
        provider_user_id=verified_identity.provider_user_id,
        provider_email=email,
        provider_name=verified_identity.name or request_data.name,
        created_at=now,
        last_login_at=now,
    )
    db.add(social_account)
    db.flush()

    return user, is_new_user, True


def _social_names(request_data: SocialLoginRequest, identity, email: str):
    """First, last and display name for a new social account.

    Google puts the names in its token. Apple does not, so the app sends what
    Apple gave it on first consent. Without either, the email's local part
    stands in, as the user can edit it later.
    """
    first = identity.given_name or request_data.first_name
    last = identity.family_name or request_data.last_name
    full = identity.name or request_data.name

    if not first and not last and full:
        first, _, last = full.partition(" ")
    if not first:
        first = email.split("@", maxsplit=1)[0]

    first = first.strip()
    last = (last or "").strip() or None
    return first, last, " ".join(part for part in (first, last) if part)


@account_entry_router.post(
    "/register/email-code",
    response_model=ApiResponse[SendEmailCodeResponse],
)
def request_register_email_code(
    request_data: RegisterEmailCodeRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Step one of sign-up: mail a code to prove the address before an account exists."""
    email = normalize_email(str(request_data.email))
    if find_user_by_email(db, email):
        raise HTTPException(status_code=400, detail="Email already registered")

    requested_ip = request.client.host if request.client else None
    result = send_email_code(
        db,
        None,
        EmailCodePurpose.register,
        email,
        requested_ip=requested_ip,
    )
    db.commit()
    return success_response(result, message="Verification code sent")


@account_entry_router.post("/register", response_model=ApiResponse[RegisterResponseData])
def register(user: UserRegister, db: Session = Depends(get_db)):
    if user.role == "admin":
        raise HTTPException(
            status_code=400,
            detail="Admin accounts cannot be created from public registration",
        )
    validate_password_policy(user.password)
    email = normalize_email(user.email)
    existing_user = find_user_by_email(db, email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    consume_email_code(db, None, EmailCodePurpose.register, email, user.email_code)
    new_user = models.User(
        name=f"{user.first_name} {user.last_name}",
        first_name=user.first_name,
        last_name=user.last_name,
        tos_accepted_at=get_now(),
        email=email,
        role=user.role,
        is_active=True,
        is_banned=False,
        last_login_at=None,
        created_at=get_now(),
        identity_verification_status=(
            "not_submitted" if user.role == "provider" else None
        ),
        qualification_verification_status=("not_submitted" if user.role == "provider" else None),
    )
    db.add(new_user)
    db.flush()
    # The mailed code above proved the address, so the account starts verified.
    create_password_identity(new_user, user.password, db, verified=True)
    db.commit()
    db.refresh(new_user)
    return success_response(
        {
            "message": "User registered successfully",
            "user": format_user_response(new_user),
        }
    )


@account_entry_router.post("/social-login", response_model=ApiResponse[SocialLoginResponseData])
def social_login(
    request_data: SocialLoginRequest,
    db: Session = Depends(get_db),
):
    user, is_new_user, linked_social_account = resolve_social_login_user(
        request_data,
        db,
    )
    access_token, refresh_token = login_user(user, db)

    return success_response(
        {
            "message": "Social login successful",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": format_user_response(user),
            "provider": request_data.provider,
            "is_new_user": is_new_user,
            "linked_social_account": linked_social_account,
        }
    )


@account_entry_router.post("/login", response_model=ApiResponse[TokenResponse])
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(form_data.username, form_data.password, db)
    access_token, refresh_token = login_user(user, db)
    return success_response(
        {
            "message": "Login successful",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": format_user_response(user),
        }
    )


@demo_router.post(
    "/demo/login",
    response_model=ApiResponse[TokenResponse],
)
def demo_login(request_data: DemoLoginRequest, db: Session = Depends(get_db)):
    user = find_user_by_email(db, DEMO_USER_EMAILS[request_data.role])
    if (
        user is None
        or user.role != request_data.role
        or not user.is_active
        or user.is_banned
        or user.email_verified_at is None
    ):
        raise HTTPException(status_code=503, detail="Demo login is unavailable")

    access_token, refresh_token = login_user(user, db)
    return success_response(
        {
            "message": "Login successful",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": format_user_response(user),
        }
    )


router.include_router(demo_router)


@account_entry_router.post("/token", response_model=OAuthTokenResponse)
def swagger_login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(form_data.username, form_data.password, db)
    access_token, refresh_token = login_user(user, db)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


router.include_router(account_entry_router)


@router.post("/refresh-token", response_model=ApiResponse[TokenResponse])
def refresh_token(request_data: RefreshTokenRequest, db: Session = Depends(get_db)):
    user, token_record = validate_refresh_token(request_data.refresh_token, db)
    token_record.revoked_at = get_now()
    access_token, new_refresh_token = create_token_pair(user, db)
    db.commit()
    return success_response(
        {
            "message": "Token refreshed successfully",
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "user": format_user_response(user),
        }
    )


@router.post("/logout", response_model=ApiResponse[None])
def logout(request_data: RefreshTokenRequest, db: Session = Depends(get_db)):
    revoke_refresh_token(request_data.refresh_token, db)
    return success_response({"message": "Logout successful"})


@router.get("/me", response_model=ApiResponse[UserResponse])
def get_me(current_user: models.User = Depends(get_current_user)):
    return success_response(format_user_response(current_user))


@router.put("/me", response_model=ApiResponse[UserResponse])
def update_me(
    profile_data: UserProfileUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role == "provider" and current_user.identity_verification_status in {
        "pending",
        "approved",
    }:
        raise HTTPException(
            status_code=409,
            detail="Name cannot be changed while identity verification is pending or approved",
        )
    current_user.name = profile_data.name
    current_user.first_name = None
    current_user.last_name = None
    db.commit()
    db.refresh(current_user)
    return success_response(
        format_user_response(current_user),
        message="User profile updated successfully",
    )


@router.patch("/me", response_model=ApiResponse[UserResponse])
def patch_me(
    profile_data: UserProfilePatch,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    changes_name = any(
        value is not None
        for value in (profile_data.name, profile_data.first_name, profile_data.last_name)
    )
    if (
        changes_name
        and current_user.role == "provider"
        and current_user.identity_verification_status in {"pending", "approved"}
    ):
        raise HTTPException(
            status_code=409,
            detail="Name cannot be changed while identity verification is pending or approved",
        )
    if profile_data.name is not None:
        current_user.name = profile_data.name
        current_user.first_name = None
        current_user.last_name = None
    elif profile_data.first_name is not None or profile_data.last_name is not None:
        first_name = profile_data.first_name or current_user.first_name
        last_name = profile_data.last_name or current_user.last_name
        if not first_name or not last_name:
            raise HTTPException(
                status_code=422,
                detail="Both first_name and last_name are required to establish a split name",
            )
        if len(f"{first_name} {last_name}") > 255:
            raise HTTPException(status_code=422, detail="Combined name is too long")
        current_user.first_name = first_name
        current_user.last_name = last_name
        current_user.name = f"{first_name} {last_name}"

    db.commit()
    db.refresh(current_user)
    return success_response(
        format_user_response(current_user),
        message="User profile updated successfully",
    )


@router.post("/me/avatar", response_model=ApiResponse[AvatarUploadResponse])
async def upload_me_avatar(
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "upload_me_avatar")
    upload_result = await save_avatar_upload(file)
    old_avatar_url = current_user.avatar_url
    current_user.avatar_url = upload_result["file_url"]
    db.commit()
    db.refresh(current_user)

    if old_avatar_url and old_avatar_url != current_user.avatar_url:
        delete_local_upload(old_avatar_url)

    return success_response(
        {
            **upload_result,
            "user": format_user_response(current_user),
        },
        message="Avatar uploaded successfully",
    )


def ensure_email_available(db: Session, email: str, current_user: models.User):
    existing_user = find_user_by_email(db, email)
    if existing_user and existing_user.id != current_user.id:
        raise HTTPException(status_code=400, detail="Email already registered")


@router.post("/auth/email-code", response_model=ApiResponse[SendEmailCodeResponse])
def request_email_code(
    request_data: SendEmailCodeRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "request_email_code")
    purpose = EmailCodePurpose(request_data.purpose)

    if purpose == EmailCodePurpose.change_email:
        email = normalize_email(str(request_data.new_email))
        if email == normalize_email(current_user.email):
            raise HTTPException(
                status_code=400,
                detail="This is already your sign-in email",
            )
        ensure_email_available(db, email, current_user)
    else:
        email = normalize_email(current_user.email)

    result = send_email_code(db, current_user, purpose, email)
    db.commit()
    return success_response(result, message="Verification code sent")


@router.post("/auth/verify-email", response_model=ApiResponse[UserResponse])
def verify_email(
    request_data: EmailCodeVerifyRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "verify_email")
    consume_email_code(
        db,
        current_user,
        EmailCodePurpose.verify_email,
        normalize_email(current_user.email),
        request_data.code,
    )
    identity = get_password_identity(current_user, db)
    mark_email_verified(current_user, identity)
    db.commit()
    db.refresh(current_user)
    return success_response(
        format_user_response(current_user),
        message="Email verified successfully",
    )


@router.post("/auth/verify-phone", response_model=ApiResponse[UserResponse])
def verify_phone(
    request_data: MockVerificationRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "verify_phone")
    if get_user_phone_number(current_user, db) is None:
        raise HTTPException(status_code=400, detail="No phone number to verify")

    mark_phone_verified(current_user)
    db.commit()
    db.refresh(current_user)
    return success_response(
        format_user_response(current_user),
        message="Phone verified successfully",
    )


@router.post("/auth/change-password", response_model=ApiResponse[UserResponse])
def change_password(
    request_data: ChangePasswordRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "change_password")
    identity = get_password_identity(current_user, db)
    if not identity or not identity.password_hash:
        raise HTTPException(status_code=400, detail="Password login is not available")
    if not verify_password(request_data.current_password, identity.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    validate_password_policy(request_data.new_password)
    identity.password_hash = hash_password(request_data.new_password)
    revoke_user_refresh_tokens(current_user, db)
    db.commit()
    db.refresh(current_user)
    return success_response(
        format_user_response(current_user),
        message="Password changed successfully",
    )


@router.post("/auth/change-email", response_model=ApiResponse[UserResponse])
def change_email(
    request_data: ChangeEmailRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "change_email")
    new_email = normalize_email(str(request_data.new_email))
    ensure_email_available(db, new_email, current_user)
    consume_email_code(
        db,
        current_user,
        EmailCodePurpose.change_email,
        new_email,
        request_data.code,
    )

    identity = get_password_identity(current_user, db)
    current_user.email = new_email
    if identity is not None:
        identity.provider_subject = new_email

    mark_email_verified(current_user, identity)
    db.commit()
    db.refresh(current_user)
    return success_response(
        format_user_response(current_user),
        message="Email changed successfully",
    )
