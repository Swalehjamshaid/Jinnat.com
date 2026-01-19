from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl

class AuditCreate(BaseModel):
    url: HttpUrl

class AuditResponse(BaseModel):
    id: int
    url: str
    score: float
    grade: str
    coverage: float
    summary: Dict[str, Any]
    metrics: Dict[str, Any]

class UserCreate(BaseModel):
    email: str = Field(..., examples=['user@example.com'])
    password: str = Field(..., min_length=6)

class UserLogin(BaseModel):
    email: str
    password: str

class UserOut(BaseModel):
    id: int
    email: str
    is_paid: bool
