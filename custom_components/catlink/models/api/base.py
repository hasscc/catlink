"""Base API response model."""

from typing import Any

from pydantic import BaseModel, ConfigDict


class ApiResponse(BaseModel):
    """Generic API response with return_code and data."""

    model_config = ConfigDict(extra="allow")

    return_code: int = 0
    data: dict[str, Any] = {}
