"""Generated file response schema."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GeneratedFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    file_type: str
    file_path: str
    mime_type: str
    created_at: datetime
