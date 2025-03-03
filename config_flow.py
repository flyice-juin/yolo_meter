"""Config flow for YOLO Meter Reader integration."""
from __future__ import annotations

import logging
import voluptuous as vol
from typing import Any

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_CAMERA_ENTITY,
    CONF_MODEL_TYPE,
    CONF_CROP_COORDS,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    MODEL_TYPE_OPTIONS,
)
from .options import YoloMeterOptionsFlow

_LOGGER = logging.getLogger(__name__)

class YoloMeterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for YOLO Meter Reader."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            return self.async_create_entry(
                title=f"YOLO {MODEL_TYPE_OPTIONS[user_input[CONF_MODEL_TYPE]]}",
                data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Required(CONF_CAMERA_ENTITY): str,
                    vol.Required(CONF_MODEL_TYPE): vol.In(list(MODEL_TYPE_OPTIONS.keys())),
                    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                        vol.Coerce(int), vol.Range(min=2)
                    ),
                    vol.Optional(CONF_CROP_COORDS): str,  # 新增裁剪坐标配置,格式: "x1,y1,x2,y2"
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return YoloMeterOptionsFlow(config_entry)
    
class YoloMeterOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for YOLO Meter Reader."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=self.config_entry.data.get(CONF_HOST),
                    ): str,
                    vol.Required(
                        CONF_PORT,
                        default=self.config_entry.data.get(CONF_PORT, DEFAULT_PORT),
                    ): int,
                    vol.Required(
                        CONF_CAMERA_ENTITY,
                        default=self.config_entry.data.get(CONF_CAMERA_ENTITY),
                    ): str,
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0)),  # 允许0值停止更新
                }
            ),
        )