"""Support for YOLO Meter Reader number inputs."""
from __future__ import annotations

import logging
from homeassistant.components.number import (
    NumberEntity,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN,
    MODEL_TYPE_OPTIONS,
    DEFAULT_BASELINE_VALUE,
)
from .coordinator import YoloMeterCoordinator

_LOGGER = logging.getLogger(__name__)
STORAGE_VERSION = 1
STORAGE_KEY_BASELINE = "yolo_meter_baseline"
STORAGE_KEY_DECIMAL = "yolo_meter_decimal"

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up YOLO Meter Reader number inputs based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        YoloMeterBaseline(coordinator, entry, hass),
        YoloMeterDecimal(coordinator, entry, hass)
    ])

class YoloMeterBaseline(CoordinatorEntity, NumberEntity):
    """Representation of a YOLO Meter Reader baseline number input."""

    def __init__(self, coordinator: YoloMeterCoordinator, entry: ConfigEntry, hass: HomeAssistant) -> None:
        """Initialize the number input."""
        super().__init__(coordinator)
        self._entry = entry
        self._hass = hass
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY_BASELINE}_{entry.entry_id}")
        model_type = entry.data['model_type']
        self._attr_name = f"YOLO {MODEL_TYPE_OPTIONS[model_type]} 基准数"
        self._attr_unique_id = f"{entry.entry_id}_baseline"
        self._attr_native_min_value = 0
        self._attr_native_max_value = 999999
        self._attr_native_step = 1
        self._attr_mode = NumberMode.BOX
        self._attr_native_value = DEFAULT_BASELINE_VALUE
        self._attr_icon = "mdi:counter"
        
        # 关联到同一个设备
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"YOLO {MODEL_TYPE_OPTIONS[model_type]}",
            manufacturer="YOLO Meter Reader",
            model=MODEL_TYPE_OPTIONS[model_type],
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        
        # 从存储中加载保存的值
        stored_data = await self._store.async_load()
        if stored_data is not None:
            self._attr_native_value = stored_data.get("value", DEFAULT_BASELINE_VALUE)
            self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        self._attr_native_value = int(value)
        # 保存值到存储
        await self._store.async_save({"value": self._attr_native_value})
        self.async_write_ha_state()

class YoloMeterDecimal(CoordinatorEntity, NumberEntity):
    """Representation of a YOLO Meter Reader decimal number input."""

    def __init__(self, coordinator: YoloMeterCoordinator, entry: ConfigEntry, hass: HomeAssistant) -> None:
        """Initialize the number input."""
        super().__init__(coordinator)
        self._entry = entry
        self._hass = hass
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY_DECIMAL}_{entry.entry_id}")
        model_type = entry.data['model_type']
        self._attr_name = f"YOLO {MODEL_TYPE_OPTIONS[model_type]} 小数位数"
        self._attr_unique_id = f"{entry.entry_id}_decimal"
        self._attr_native_min_value = 0
        self._attr_native_max_value = 9
        self._attr_native_step = 1
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_value = 0
        self._attr_icon = "mdi:decimal"
        
        # 关联到同一个设备
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"YOLO {MODEL_TYPE_OPTIONS[model_type]}",
            manufacturer="YOLO Meter Reader",
            model=MODEL_TYPE_OPTIONS[model_type],
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        
        # 从存储中加载保存的值
        stored_data = await self._store.async_load()
        if stored_data is not None:
            self._attr_native_value = stored_data.get("value", 0)
            self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        self._attr_native_value = int(value)
        # 保存值到存储
        await self._store.async_save({"value": self._attr_native_value})
        self.async_write_ha_state()