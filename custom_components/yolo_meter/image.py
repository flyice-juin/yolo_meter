"""Support for YOLO Meter Reader images."""
from __future__ import annotations

from datetime import datetime
import zoneinfo
from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import base64
import secrets

from .const import (
    DOMAIN,
    MODEL_TYPE_OPTIONS,
)
from .coordinator import YoloMeterCoordinator

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up YOLO Meter Reader image based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([YoloMeterImage(coordinator, entry)])

class YoloMeterImage(CoordinatorEntity, ImageEntity):
    """Representation of a YOLO Meter Reader result image."""

    def __init__(self, coordinator: YoloMeterCoordinator, entry: ConfigEntry) -> None:
        """Initialize the image."""
        super().__init__(coordinator)
        self._entry = entry
        model_type = entry.data['model_type']
        self._attr_name = f"YOLO {MODEL_TYPE_OPTIONS[model_type]} Image"
        self._attr_unique_id = f"{entry.entry_id}_image"
        self._access_token = secrets.token_hex()
        self._attr_icon = "mdi:image-search"  # 添加图标
        
        # 关联到同一个设备
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"YOLO {MODEL_TYPE_OPTIONS[model_type]}",
            manufacturer="YOLO Meter Reader",
            model=MODEL_TYPE_OPTIONS[model_type],
        )

    @property
    def image_last_updated(self):
        """Return the last update timestamp."""
        if self.coordinator.last_update_success_time:
            # 转换为本地时区
            return self.coordinator.last_update_success_time.astimezone(
                zoneinfo.ZoneInfo(self.hass.config.time_zone)
            )
        return None

    @property
    def access_tokens(self):
        """Return access tokens for the image."""
        return [self._access_token]

    async def async_image(self):
        """Return bytes of image."""
        if self.coordinator.data and self.coordinator.data.get("result_image"):
            return base64.b64decode(self.coordinator.data["result_image"])
        return None