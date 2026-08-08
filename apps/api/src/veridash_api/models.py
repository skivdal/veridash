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


class RenameProjectRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, title: str) -> str:
        normalized = title.strip()
        if not normalized:
            raise ValueError("title must not be blank")
        return normalized


class ReserveSourceMediaRequest(BaseModel):
    original_filename: str = Field(min_length=1, max_length=512)

    @field_validator("original_filename")
    @classmethod
    def normalize_filename(cls, filename: str) -> str:
        normalized = filename.strip()
        if not normalized or any(ord(character) < 32 for character in normalized):
            raise ValueError("original filename contains invalid characters")
        return normalized


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    state: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    archived_at: datetime.datetime | None


class SourceMediaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    upload_state: str
    original_filename: str
    media_type: str | None
    size_bytes: int | None
    sha256_hex: str | None
    created_at: datetime.datetime
    uploaded_at: datetime.datetime | None
    failure_message: str | None


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
