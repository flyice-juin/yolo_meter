"""Options flow handler for YOLO Meter Reader."""
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
    CONF_CROP_COORDS,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

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
                    vol.Optional(
                        CONF_CROP_COORDS,
                        description={"suggested_value": self.config_entry.data.get(CONF_CROP_COORDS, "")},
                    ): str,
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0)),
                }
            ),
        )
