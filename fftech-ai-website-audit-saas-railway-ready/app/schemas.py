from pydantic import BaseModel, HttpUrl, ConfigDict
from typing import List, Optional

class AuditBase(BaseModel):
    url: HttpUrl

class OpenAuditRequest(BaseModel):
    url: HttpUrl
    # V2 Config: Removes UserWarning
    model_config = ConfigDict(from_attributes=True)

class AuditOut(AuditBase):
    id: int
    result_json: Optional[dict] = None
    # FIXED: Replaces 'orm_mode = True'
    model_config = ConfigDict(from_attributes=True)

class AuditCreate(AuditBase):
    competitors: Optional[List[HttpUrl]] = None
    model_config = ConfigDict(from_attributes=True)
