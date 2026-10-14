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
    evidence_basis: Literal['explicit_statement', 'absence_of_evidence', 'uncertain'] = 'uncertain'


class ReportArgs(BaseModel):
    assessments: list[Assessment]
    summary: str = Field(max_length=3000)


class RepositoryArgs(BaseModel):
    repository: str


class SearchArgs(BaseModel):
    query: str = Field(min_length=1, max_length=200)


class DocumentArgs(RepositoryArgs):
    path: str = Field(min_length=1, max_length=300)


class IssueArgs(RepositoryArgs):
    query: str = Field(default='', max_length=200)


class GapTarget(RepositoryArgs):
    requirement_id: str
    query: str = Field(min_length=1, max_length=200)
    document_path: str | None = Field(default=None, max_length=300)


class FollowupArgs(BaseModel):
    targets: list[GapTarget] = Field(min_length=1, max_length=3, description='每个 repository + requirement_id 组合在本轮只能出现一次。多个关键词放在同一个 query 中；不要为同一条件创建多个目标。')
