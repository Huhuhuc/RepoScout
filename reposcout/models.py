from typing import Literal
from pydantic import BaseModel, Field


class Requirement(BaseModel):
    id: str
    text: str = Field(min_length=1, max_length=300)
    mandatory: bool = True


class TaskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    requirements: list[Requirement] = Field(min_length=1, max_length=8)
    repositories: list[str] = Field(default_factory=list, max_length=3)
    mode: Literal['demo', 'github', 'deepseek'] = 'demo'
    max_tools: int = Field(default=20, ge=1, le=40)


class EvidenceArgs(BaseModel):
    source_id: str
    requirement_id: str
    quote: str = Field(min_length=1, max_length=1200)


class Assessment(BaseModel):
    repository: str
    requirement_id: str
    status: Literal['supported', 'unsupported', 'unknown', 'conflict']
    explanation: str = Field(max_length=1000)
    evidence_ids: list[str] = Field(default_factory=list)


class ReportArgs(BaseModel):
    assessments: list[Assessment]
    summary: str = Field(max_length=3000)


class RepositoryArgs(BaseModel):
    repository: str


class SearchArgs(BaseModel):
    query: str = Field(min_length=1, max_length=200)
