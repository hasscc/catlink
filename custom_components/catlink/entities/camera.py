"""Camera entities for CatLink integration."""

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, cast

from homeassistant.components.camera import Camera

from .base import CatlinkEntity

if TYPE_CHECKING:
    from ..devices.base import Device


class CatlinkCameraEntity(Camera, CatlinkEntity):
    """A still-image camera backed by a device callback."""

    def __init__(self, name, device: "Device", option=None) -> None:
        Camera.__init__(self)
        CatlinkEntity.__init__(self, name, device, option)
        self.content_type = "image/jpeg"

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a privacy-safe event image."""
        callback = self._option.get("async_image")
        if not callable(callback):
            return None
        image_callback = cast(Callable[[], Awaitable[bytes | None]], callback)
        return await image_callback()
