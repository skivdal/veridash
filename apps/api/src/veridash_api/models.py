"""HTTP request and response models, intentionally separate from SQLc rows."""

import datetime
import re
import uuid

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

DASHBOARD_MODULE_IDS = (
    "source",
    "frames",
    "transcription",
    "detection",
    "metadata",
    "map",
    "notes",
    "activity",
)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=1024)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024, repr=False)
    new_password: str = Field(min_length=12, max_length=1024, repr=False)
    confirm_password: str = Field(min_length=12, max_length=1024, repr=False)

    @model_validator(mode="after")
    def validate_confirmation(self) -> "ChangePasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("new passwords must match")
        return self


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_admin: bool


class SessionResponse(BaseModel):
    user: UserResponse


class CreateManagedUserRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=1024)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, username: str) -> str:
        normalized = username.strip().lower()
        if not normalized:
            raise ValueError("username must not be blank")
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_email(cls, email: str) -> str:
        normalized = email.strip().lower()
        if re.fullmatch(r"[^\s@]+@[^\s@]+", normalized) is None:
            raise ValueError("email address is invalid")
        return normalized


class AdminUserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_enabled: bool
    is_admin: bool
    last_login_at: datetime.datetime | None
    project_count: int
    created_at: datetime.datetime


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


class SaveProjectNoteRequest(BaseModel):
    body: str = Field(max_length=100_000)
    expected_revision: int = Field(ge=0)


class ProjectNoteResponse(BaseModel):
    project_id: uuid.UUID
    body: str
    revision: int
    updated_at: datetime.datetime


class SaveDashboardPreferenceRequest(BaseModel):
    module_order: list[str] = Field(min_length=8, max_length=8)
    hidden_modules: list[str] = Field(max_length=8)
    expected_revision: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_modules(self) -> "SaveDashboardPreferenceRequest":
        expected = set(DASHBOARD_MODULE_IDS)
        if len(self.module_order) != len(set(self.module_order)):
            raise ValueError("dashboard module order must be unique")
        if set(self.module_order) != expected:
            raise ValueError("dashboard module order must contain every supported module")
        if len(self.hidden_modules) != len(set(self.hidden_modules)):
            raise ValueError("hidden dashboard modules must be unique")
        if not set(self.hidden_modules) <= expected:
            raise ValueError("hidden dashboard modules contain an unsupported module")
        return self


class DashboardPreferenceResponse(BaseModel):
    user_id: int
    module_order: list[str]
    hidden_modules: list[str]
    revision: int
    updated_at: datetime.datetime


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


class AnalysisAttemptResponse(BaseModel):
    id: uuid.UUID
    attempt_number: int
    state: str
    progress_stage: str | None
    progress_completed: int | None
    progress_total: int | None
    progress_message: str | None
    progress_at: datetime.datetime | None
    heartbeat_at: datetime.datetime
    error_kind: str | None
    public_error_message: str | None
    diagnostic_id: uuid.UUID | None
    started_at: datetime.datetime
    finished_at: datetime.datetime | None


class AnalysisJobResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    source_media_id: uuid.UUID
    module_id: str
    implementation_version: str
    result_schema_version: int
    display_name: str
    resource_class: str
    cacheable: bool
    implementation_fingerprints: dict[str, str]
    state: str
    parameters: dict[str, object]
    max_attempts: int
    next_attempt_at: datetime.datetime | None
    ready_at: datetime.datetime | None
    started_at: datetime.datetime | None
    finished_at: datetime.datetime | None
    cancel_requested_at: datetime.datetime | None
    failure_kind: str | None
    public_failure_message: str | None
    diagnostic_id: uuid.UUID | None
    reused: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    attempts: list[AnalysisAttemptResponse]


class AnalysisArtifactResponse(BaseModel):
    id: uuid.UUID
    output_name: str
    kind: str
    sha256_hex: str
    size_bytes: int
    media_type: str
    json_payload: JsonValue | None
    schema_id: str
    schema_version: int
    created_at: datetime.datetime


class ProjectEventResponse(BaseModel):
    id: int
    project_id: uuid.UUID
    job_id: uuid.UUID | None
    attempt_id: uuid.UUID | None
    event_type: str
    source: str
    payload_version: int
    payload: JsonValue
    created_at: datetime.datetime


class CreateFrameStitchRequest(BaseModel):
    selected_output_names: list[str] = Field(min_length=2, max_length=12)

    @field_validator("selected_output_names")
    @classmethod
    def validate_selected_frames(cls, names: list[str]) -> list[str]:
        from veridash_analysis.stitching import StitchFramesParameters

        return StitchFramesParameters(selected_output_names=names).selected_output_names


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
