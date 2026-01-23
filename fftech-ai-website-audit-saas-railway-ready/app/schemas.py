from pydantic import BaseModel, HttpUrl, ConfigDict
from typing import List, Optional

class AuditBase(BaseModel):
    url: HttpUrl

class AuditCreate(AuditBase):
    competitors: Optional[List[HttpUrl]] = None

class OpenAuditRequest(BaseModel):
    url: HttpUrl
    
    # FIXED: Removes UserWarning by using v2 syntax
    model_config = ConfigDict(from_attributes=True)

class AuditOut(AuditBase):
    id: int
    result_json: Optional[dict] = None
    
    # FIXED: Replaces 'orm_mode = True'
    model_config = ConfigDict(from_attributes=True)

class UserBase(BaseModel):
    email: str

class UserOut(UserBase):
    id: int
    is_verified: bool
    audit_count: int
    plan: str
    
    model_config = ConfigDict(from_attributes=True)
