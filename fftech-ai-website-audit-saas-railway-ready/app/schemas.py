from pydantic import BaseModel, HttpUrl, ConfigDict
from typing import List, Optional

class AuditBase(BaseModel):
    url: HttpUrl

class OpenAuditRequest(BaseModel):
    url: HttpUrl
    model_config = ConfigDict(from_attributes=True)

class AuditOut(AuditBase):
    id: int
    result_json: Optional[dict] = None
    model_config = ConfigDict(from_attributes=True)

class AuditCreate(AuditBase):
    competitors: Optional[List[HttpUrl]] = None
