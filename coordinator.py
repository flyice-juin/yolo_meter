"""DataUpdateCoordinator for YOLO Meter Reader integration."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import timedelta, datetime
import aiohttp
import base64
from PIL import Image
import io

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.components.camera import async_get_image

from .const import (
    DOMAIN,
    CONF_CAMERA_ENTITY,
    CONF_MODEL_TYPE,
    CONF_CROP_COORDS,
    DEFAULT_DETECT_FOLDER,
    DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)
MAX_RETRY_ATTEMPTS = 5
RETRY_DELAY = 2  # seconds

class YoloMeterCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the YOLO Meter Reader server."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.hass = hass
        self.entry = entry
        self.host = entry.data[CONF_HOST]
        self.port = entry.data[CONF_PORT]
        self.camera_entity = entry.data[CONF_CAMERA_ENTITY]
        self.model_type = entry.data[CONF_MODEL_TYPE]
        self.last_update_success_time = None
        self._failed_attempts = 0
        
        # Ensure detect folder exists
        self.detect_folder = os.path.join(hass.config.path("www"), DEFAULT_DETECT_FOLDER)
        if not os.path.exists(self.detect_folder):
            os.makedirs(self.detect_folder)

        scan_interval = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval),
        )

    @property
    def crop_coords(self):
        """Get current crop coordinates from config entry."""
        return self.entry.options.get(CONF_CROP_COORDS) or self.entry.data.get(CONF_CROP_COORDS)

    def crop_image(self, image_path: str) -> str:
        """Crop image if coordinates are set."""
        coords = self.crop_coords
        if not coords:
            return image_path

        try:
            # Parse coordinates
            x1, y1, x2, y2 = map(float, coords.split(','))
            
            # Open and crop image
            with Image.open(image_path) as img:
                width, height = img.size
                crop_box = (
                    int(x1 * width),
                    int(y1 * height),
                    int(x2 * width),
                    int(y2 * height)
                )
                _LOGGER.debug(f"Cropping image with coordinates: {crop_box}")
                cropped = img.crop(crop_box)
                
                # Save cropped image
                cropped_path = image_path.replace('.jpg', '_cropped.jpg')
                cropped.save(cropped_path)
                return cropped_path
        except Exception as err:
            _LOGGER.error(f"Error cropping image: {err}")
            return image_path

    async def take_snapshot(self, image_path: str) -> bool:
        """Take a snapshot with retry mechanism."""
        try:
            await self.hass.services.async_call(
                "camera",
                "snapshot",
                {
                    "entity_id": self.camera_entity,
                    "filename": image_path
                }
            )
            await asyncio.sleep(RETRY_DELAY)
            return os.path.exists(image_path)
        except Exception as err:
            _LOGGER.error(f"Error taking snapshot: {err}")
            return False

    async def _async_update_data(self):
        """Update data via API."""
        try:
            # Get latest configuration from options
            self.host = self.entry.options.get(CONF_HOST, self.entry.data[CONF_HOST])
            self.port = self.entry.options.get(CONF_PORT, self.entry.data[CONF_PORT])
            self.camera_entity = self.entry.options.get(CONF_CAMERA_ENTITY, self.entry.data[CONF_CAMERA_ENTITY])

            # Clean up old images
            image_path = os.path.join(
                self.detect_folder,
                f"{self.camera_entity.split('.')[-1]}.jpg"
            )
            cropped_path = image_path.replace('.jpg', '_cropped.jpg')
            
            for path in [image_path, cropped_path]:
                if os.path.exists(path):
                    os.remove(path)

            # Take snapshot with retries
            snapshot_success = False
            for attempt in range(MAX_RETRY_ATTEMPTS):
                if await self.take_snapshot(image_path):
                    snapshot_success = True
                    self._failed_attempts = 0  # Reset failed attempts counter
                    break
                _LOGGER.warning(f"Failed to take snapshot, attempt {attempt + 1} of {MAX_RETRY_ATTEMPTS}")
                await asyncio.sleep(RETRY_DELAY)

            if not snapshot_success:
                self._failed_attempts += 1
                if self._failed_attempts >= MAX_RETRY_ATTEMPTS:
                    raise UpdateFailed("Failed to take camera snapshot after multiple attempts")
                # 如果失败次数未达到最大值，返回上次的数据
                return self.data if self.data else None

            # Crop image if coordinates are set
            send_image_path = self.crop_image(image_path)
            _LOGGER.debug(f"Using image path for detection: {send_image_path}")

            # Send request to YOLO server
            url = f"http://{self.host}:{self.port}/detect/{self.model_type}"
            
            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                data.add_field(
                    'file',
                    open(send_image_path, 'rb'),
                    filename='image.jpg',
                    content_type='image/jpeg'
                )
                data.add_field('request_id', self.entry.entry_id)

                async with session.post(url, data=data) as response:
                    if response.status != 200:
                        raise UpdateFailed(f"Error from YOLO server: {await response.text()}")
                    
                    result = await response.json()
                    if result.get('success'):
                        self.last_update_success_time = datetime.now()
                    return result

        except Exception as err:
            self._failed_attempts += 1
            if self._failed_attempts >= MAX_RETRY_ATTEMPTS:
                raise UpdateFailed(f"Error communicating with YOLO server: {err}")
            # 如果失败次数未达到最大值，返回上次的数据
            return self.data if self.data else None