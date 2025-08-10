"""Support for YOLO Meter Reader sensors."""
from __future__ import annotations

from datetime import datetime
import zoneinfo
from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from .const import (
    DOMAIN,
    ATTR_DETECTED_NUMBER,
    ATTR_SUCCESS,
    MODEL_TYPE_OPTIONS,
    ATTR_LAST_UPDATE,
)
from .coordinator import YoloMeterCoordinator

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up YOLO Meter Reader sensor based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([YoloMeterSensor(coordinator, entry)])

class YoloMeterSensor(CoordinatorEntity, SensorEntity):
    """Representation of a YOLO Meter Reader sensor."""

    def __init__(self, coordinator: YoloMeterCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        model_type = entry.data['model_type']
        self._attr_name = f"YOLO {MODEL_TYPE_OPTIONS[model_type]}"
        self._attr_unique_id = f"{entry.entry_id}_meter"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_available = True  # 始终保持可用状态
        self._attr_icon = "mdi:numeric"  # 添加图标
        
        # 设置设备信息
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"YOLO {MODEL_TYPE_OPTIONS[model_type]}",
            manufacturer="YOLO Meter Reader",
            model=MODEL_TYPE_OPTIONS[model_type],
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data and self.coordinator.data.get(ATTR_SUCCESS):
            return self.coordinator.data.get(ATTR_DETECTED_NUMBER)
        return self._attr_native_value  # 保持上一次的值

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = {}
        if self.coordinator.data:
            attrs[ATTR_SUCCESS] = self.coordinator.data.get(ATTR_SUCCESS)
        if self.coordinator.last_update_success_time:
            # 转换为本地时区
            local_time = self.coordinator.last_update_success_time.astimezone(
                zoneinfo.ZoneInfo(self.hass.config.time_zone)
            )
            attrs[ATTR_LAST_UPDATE] = local_time.isoformat()
        return attrs