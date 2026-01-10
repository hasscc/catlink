"""Log API models."""

from pydantic import BaseModel, ConfigDict


class LogEntry(BaseModel):
    """Log entry from device logs API."""

    model_config = ConfigDict(extra="allow")

    time: str = ""
    event: str = ""
    firstSection: str = ""
    secondSection: str = ""
    errkey: str = ""
