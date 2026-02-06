"""Parse helpers for API responses."""

from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


def parse_response(
    data: dict,
    key: str,
    model: type[T],
    default: Any = None,
) -> T | dict | list | Any:
    """Parse API response data into a Pydantic model with fallback to raw value."""
    raw = data.get(key) if data else None
    if raw is None:
        return default
    try:
        if isinstance(raw, list):
            return [model.model_validate(item) for item in raw]
        return model.model_validate(raw)
    except ValidationError:
        return raw if default is None else default
