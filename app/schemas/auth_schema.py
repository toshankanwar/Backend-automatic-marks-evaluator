from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional


class SignupRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    user_id: str
    name: str
    email: EmailStr
    access_token: str
    token_type: str = "bearer"

  # -------- NEW --------
class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, v: str):
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(not c.isalnum() for c in v)
        if not (has_upper and has_lower and has_digit and has_special):
            raise ValueError("Password must include upper, lower, digit, and special character.")
        return v


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)


class ProfileResponse(BaseModel):
    user_id: str
    name: str
    email: EmailStr
    created_at: Optional[str] = None


class UpdateProfileRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=8, max_length=128)
    confirm_text: str  