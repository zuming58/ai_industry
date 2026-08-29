from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    customer_code: str | None = Field(default=None, max_length=80)
    plc_brand: str = Field(default="三菱电机", max_length=80)
    plc_series: str = Field(default="MELSEC iQ-F", max_length=80)
    plc_model: str = Field(default="FX5U-64MT/ES", max_length=120)


class ProjectPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=160)
    customer_code: str | None = Field(default=None, max_length=80)
    plc_brand: str | None = Field(default=None, max_length=80)
    plc_series: str | None = Field(default=None, max_length=80)
    plc_model: str | None = Field(default=None, max_length=120)
    expected_revision: int | None = Field(default=None, ge=1)


class CellEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sheet: str
    row: int = Field(ge=2)
    column: str
    value: Any = None


class CellPatchRequest(BaseModel):
    edits: list[CellEdit] = Field(min_length=1, max_length=100)
    expected_revision: int | None = Field(default=None, ge=1)


class WarningAcceptRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    expected_revision: int | None = Field(default=None, ge=1)


class ConfirmationRequest(BaseModel):
    confirmed_by: str = Field(default="本机工程师", min_length=1, max_length=120)
    expected_revision: int | None = Field(default=None, ge=1)


class GenerationRequest(BaseModel):
    spec_revision_id: str | None = None
    branch_name: str | None = Field(default=None, min_length=2, max_length=120)


class BranchCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    base_commit: str | None = Field(default=None, max_length=64)


class ProgramFilePatch(BaseModel):
    content: str = Field(max_length=2_000_000)
    reason: str = Field(min_length=3, max_length=500)
    expected_revision: int = Field(ge=1)


class ProgramCommitRequest(BaseModel):
    message: str = Field(min_length=3, max_length=240)
    author: str = Field(default="本机工程师", min_length=1, max_length=120)
    expected_revision: int = Field(ge=1)
