"""HTTP request and response models, intentionally separate from SQLc rows."""

import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=1024)


class UserResponse(BaseModel):
    id: int
    username: str


class SessionResponse(BaseModel):
    user: UserResponse


class CreateProjectRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, title: str) -> str:
        normalized = title.strip()
        if not normalized:
            raise ValueError("title must not be blank")
        return normalized


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    state: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    archived_at: datetime.datetime | None


class ProblemResponse(BaseModel):
    """Safe RFC problem-details-style response shared by every API error."""

    model_config = ConfigDict(populate_by_name=True)

    type: str
    title: str
    status: int
    detail: str
    code: str
    diagnostic_id: str | None = Field(default=None, alias="diagnosticId")


PROBLEM_RESPONSE = {"model": ProblemResponse}
