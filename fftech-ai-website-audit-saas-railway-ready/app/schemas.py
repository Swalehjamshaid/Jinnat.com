
from pydantic import BaseModel, EmailStr, HttpUrl
from typing import Optional, Dict, Any
from datetime import datetime

class UserOut(BaseModel):
    id: int
    email: EmailStr
    plan: str
    audit_count: int
    is_verified: bool
    created_at: datetime
    class Config:
        orm_mode = True

class AuditCreate(BaseModel):
    url: HttpUrl
    competitors: Optional[list[HttpUrl]] = None

class AuditOut(BaseModel):
    id: int
    url: HttpUrl
    created_at: datetime
    result_json: Dict[str, Any]
    class Config:
        orm_mode = True

class OpenAuditRequest(BaseModel):
    url: HttpUrl
