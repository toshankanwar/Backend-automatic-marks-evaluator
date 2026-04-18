from pydantic import BaseModel, EmailStr, Field

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