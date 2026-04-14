from datetime import datetime

from pydantic import BaseModel, Field

from app.models import LayerSourceType, UserRole


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    login: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class UserPublic(BaseModel):
    id: int
    login: str
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    login: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=8, max_length=256)
    role: UserRole = UserRole.viewer


class LayerBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class LayerCreateUrl(LayerBase):
    source_url: str = Field(min_length=1, max_length=2048)


class LayerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


class LayerOut(BaseModel):
    id: int
    name: str
    description: str | None
    source_type: LayerSourceType
    created_at: datetime

    model_config = {"from_attributes": True}
