from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AccountOut(BaseModel):
    id: UUID
    email: str
    display_name: str

    model_config = {"from_attributes": True}


class DevSessionIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)


class ProjectCreate(BaseModel):
    brief: str = Field(min_length=1, max_length=8000)
    name: str | None = Field(default=None, max_length=120)

    @field_validator("brief")
    @classmethod
    def brief_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("brief cannot be blank")
        return stripped


class ProjectUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name cannot be blank")
        return stripped


class ProjectOut(BaseModel):
    id: UUID
    name: str
    brief: str
    phase: str
    planning_doc_version: int = 0
    requirements_doc_version: int = 0
    planning_redraft_active: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    content: str = Field(default="", max_length=8000)
    skipped: bool = False
    # True when the user submitted via the active question card (chip/submit).
    # Binds the message as an answer to the current interview area — never an aside.
    bound_to_question: bool = False
    tab: str | None = None
    # "No, keep it here" on a phase_redirect_suggestion widget (D89) resubmits
    # the same content bypassing that one check, so it records normally.
    skip_redirect_check: bool = False

    @field_validator("content")
    @classmethod
    def content_strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("tab")
    @classmethod
    def tab_ok(cls, value: str | None) -> str | None:
        if value in (None, ""):
            return None
        if value not in ("planning", "requirements"):
            raise ValueError("tab must be planning or requirements")
        return value


class GateActionIn(BaseModel):
    action: str = Field(pattern="^(accept|revise|select_packs|redraft|planning_redraft)$")
    content: str = Field(default="", max_length=4000)
    area: str | None = None
    pack_ids: list[str] = Field(default_factory=list)
    pack_mode: str | None = None
    tab: str | None = None

    @field_validator("pack_mode")
    @classmethod
    def pack_mode_ok(cls, value: str | None) -> str | None:
        # D84: Requirements is separate-only; accept legacy "combined" by coercing.
        if value is None or value == "":
            return "separate"
        if value in ("combined", "separate"):
            return "separate"
        raise ValueError("pack_mode must be separate")

    @field_validator("tab")
    @classmethod
    def tab_ok(cls, value: str | None) -> str | None:
        if value in (None, ""):
            return None
        if value not in ("planning", "requirements"):
            raise ValueError("tab must be planning or requirements")
        return value


class ChatStateOut(BaseModel):
    tab: str
    writable: bool
    mode: str
    thread_key: str
    requirements_stale_since: datetime | None = None


class MessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    widget: dict | None
    phase: str = "planning"
    thread_key: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}


class CardOut(BaseModel):
    id: UUID
    kind: str
    coverage_area: str | None
    body: str
    status: str
    version: int
    created_at: datetime
    sources: list[str] = []

    model_config = {"from_attributes": True}


class CardUpdateIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class LinkIn(BaseModel):
    url: str = Field(min_length=10, max_length=2000)


class SnapshotOut(BaseModel):
    id: UUID
    phase: str
    document: str
    body: str
    narrative: str | None = None
    narratives: dict | None = None
    accepted_by_account_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class UploadOut(BaseModel):
    id: UUID
    filename: str
    content_type: str
    status: str
    speaker_name: str | None
    last_error: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConflictResolveIn(BaseModel):
    winner_card_id: UUID


class FeasibilityIn(BaseModel):
    query: str = Field(min_length=3, max_length=500)


class TranscribeOut(BaseModel):
    text: str
