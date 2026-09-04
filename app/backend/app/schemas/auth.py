from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    display_name: str


class CurrentUser(BaseModel):
    username: str
    display_name: str
