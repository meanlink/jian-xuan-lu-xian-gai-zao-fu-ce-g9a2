from typing import Literal
from pydantic import BaseModel, Field


class LineOrderInput(BaseModel):
    team: str = Field(min_length=1, max_length=40)
    to_line: str = Field(min_length=1, max_length=40)
    job_id: int
    note: str = Field(default='', max_length=300)


class HandoverInput(BaseModel):
    side: Literal['from', 'to']
    receipt_id: str = Field(min_length=8, max_length=80, pattern=r'^[A-Za-z0-9._:-]+$')
    note: str = Field(default='', max_length=300)
    occurred_at: float | None = Field(default=None, ge=0)


class CancelInput(BaseModel):
    reason: str = Field(min_length=2, max_length=300)
