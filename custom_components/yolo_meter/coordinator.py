"""DataUpdateCoordinator for YOLO Meter Reader integration."""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import tempfile
from datetime import timedelta, datetime
import aiohttp
import base64
from PIL import Image
import io
from functools import partial

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
    CONF_RTSP_URL,
    CONF_MODEL_TYPE,
    CONF_CROP_COORDS,
    DEFAULT_DETECT_FOLDER,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_RTSP_TIMEOUT,
    DEFAULT_MAX_RETRIES,
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
        self.camera_entity = entry.data.get(CONF_CAMERA_ENTITY)
        self.rtsp_url = entry.data.get(CONF_RTSP_URL)
        self.model_type = entry.data[CONF_MODEL_TYPE]
        self.last_update_success_time = None
        self._failed_attempts = 0
        
        # Ensure detect folder exists
        self.detect_folder = os.path.join(hass.config.path("www"), DEFAULT_DETECT_FOLDER)
        # 使用 executor 创建目录
        if not os.path.exists(self.detect_folder):
            hass.async_add_executor_job(os.makedirs, self.detect_folder)

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

    async def crop_image(self, image_path: str) -> str:
        """Crop image if coordinates are set."""
        coords = self.crop_coords
        if not coords:
            return image_path

        try:
            # Parse coordinates
            x1, y1, x2, y2 = map(float, coords.split(','))
            
            def _do_crop():
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

            # 在 executor 中执行图片裁剪
            return await self.hass.async_add_executor_job(_do_crop)
        except Exception as err:
            _LOGGER.error(f"Error cropping image: {err}")
            return image_path

    async def capture_rtsp_frame(self) -> bytes | None:
        """Capture frame from RTSP stream using FFmpeg."""
        if not self.rtsp_url:
            _LOGGER.error("RTSP URL not configured")
            return None
            
        def _capture_frame_ffmpeg():
            """Capture frame using FFmpeg in executor thread."""
            retry_count = 0
            max_retries = DEFAULT_MAX_RETRIES
            
            while retry_count < max_retries:
                try:
                    _LOGGER.debug(f"Attempting to capture frame from RTSP stream: {self.rtsp_url} (attempt {retry_count + 1})")
                    
                    # 创建临时文件保存图片
                    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                        temp_path = temp_file.name
                    
                    try:
                        # 构建FFmpeg命令
                        ffmpeg_cmd = [
                            'ffmpeg',
                            '-y',  # 覆盖输出文件
                            '-rtsp_transport', 'tcp',  # 使用TCP传输
                            '-i', self.rtsp_url,  # 输入RTSP流
                            '-frames:v', '1',  # 只获取一帧
                            '-q:v', '2',  # 高质量
                            '-f', 'image2',  # 输出格式为图片
                            temp_path  # 输出文件路径
                        ]
                        
                        # 执行FFmpeg命令
                        result = subprocess.run(
                            ffmpeg_cmd,
                            capture_output=True,
                            text=True,
                            timeout=DEFAULT_RTSP_TIMEOUT,
                            check=False
                        )
                        
                        if result.returncode == 0 and os.path.exists(temp_path):
                            # 读取生成的图片文件
                            with open(temp_path, 'rb') as f:
                                image_data = f.read()
                            
                            if image_data:
                                _LOGGER.debug("Successfully captured frame from RTSP stream using FFmpeg")
                                return image_data
                            else:
                                _LOGGER.warning(f"Generated image file is empty (attempt {retry_count + 1})")
                        else:
                            _LOGGER.warning(f"FFmpeg failed (attempt {retry_count + 1}): {result.stderr}")
                    
                    finally:
                        # 清理临时文件
                        if os.path.exists(temp_path):
                            os.unlink(temp_path)
                    
                except subprocess.TimeoutExpired:
                    _LOGGER.warning(f"FFmpeg timeout (attempt {retry_count + 1})")
                except Exception as e:
                    _LOGGER.error(f"Error capturing RTSP frame with FFmpeg (attempt {retry_count + 1}): {e}")
                
                retry_count += 1
                if retry_count < max_retries:
                    import time
                    time.sleep(1)  # 等待1秒后重试
            
            _LOGGER.error(f"Failed to capture frame after {max_retries} attempts")
            return None
        
        try:
            # 在executor中执行FFmpeg操作
            return await self.hass.async_add_executor_job(_capture_frame_ffmpeg)
        except Exception as err:
            _LOGGER.error(f"Error in FFmpeg RTSP capture: {err}")
            return None

    async def take_snapshot(self) -> bytes | None:
        """Take a snapshot using either RTSP or Home Assistant camera entity."""
        # 优先使用RTSP流
        if self.rtsp_url:
            return await self.capture_rtsp_frame()
        
        # 回退到使用Home Assistant摄像头实体
        if not self.camera_entity:
            _LOGGER.error("Neither RTSP URL nor camera entity configured")
            return None
            
        try:
            # 使用 async_get_image 替代 camera.snapshot 服务
            image = await async_get_image(self.hass, self.camera_entity)
            if image:
                return image.content
            return None
        except Exception as err:
            _LOGGER.error(f"Error taking snapshot: {err}")
            return None

    async def _async_update_data(self):
        """Update data via API."""
        try:
            # Get latest configuration from options
            self.host = self.entry.options.get(CONF_HOST, self.entry.data[CONF_HOST])
            self.port = self.entry.options.get(CONF_PORT, self.entry.data[CONF_PORT])
            self.camera_entity = self.entry.options.get(CONF_CAMERA_ENTITY, self.entry.data.get(CONF_CAMERA_ENTITY))
            self.rtsp_url = self.entry.options.get(CONF_RTSP_URL, self.entry.data.get(CONF_RTSP_URL))

            # Clean up old images
            entity_name = "rtsp_stream"
            if self.camera_entity:
                entity_name = self.camera_entity.split('.')[-1]
            elif self.rtsp_url:
                # 从RTSP URL中提取一个简单的名称
                entity_name = "rtsp_stream"
                
            image_path = os.path.join(
                self.detect_folder,
                f"{entity_name}.jpg"
            )
            cropped_path = image_path.replace('.jpg', '_cropped.jpg')
            
            # 在 executor 中执行文件操作
            def _cleanup_files():
                for path in [image_path, cropped_path]:
                    if os.path.exists(path):
                        os.remove(path)
            
            await self.hass.async_add_executor_job(_cleanup_files)

            # Take snapshot with retries
            snapshot_success = False
            snapshot_data = None
            
            for attempt in range(MAX_RETRY_ATTEMPTS):
                snapshot_data = await self.take_snapshot()
                if snapshot_data:
                    snapshot_success = True
                    self._failed_attempts = 0  # Reset failed attempts counter
                    break
                _LOGGER.warning(f"Failed to take snapshot, attempt {attempt + 1} of {MAX_RETRY_ATTEMPTS}")
                await asyncio.sleep(RETRY_DELAY)

            if not snapshot_success:
                self._failed_attempts += 1
                if self._failed_attempts >= MAX_RETRY_ATTEMPTS:
                    raise UpdateFailed("Failed to take camera snapshot after multiple attempts")
                return self.data if self.data else None

            # 在 executor 中保存图片
            def _save_image():
                with open(image_path, 'wb') as f:
                    f.write(snapshot_data)
                return image_path

            saved_image_path = await self.hass.async_add_executor_job(_save_image)
            
            # Crop image if coordinates are set
            send_image_path = await self.crop_image(saved_image_path)
            _LOGGER.debug(f"Using image path for detection: {send_image_path}")

            # Send request to YOLO server
            url = f"http://{self.host}:{self.port}/detect/{self.model_type}"
            
            # 在 executor 中读取文件
            def _read_file():
                with open(send_image_path, 'rb') as f:
                    return f.read()

            file_data = await self.hass.async_add_executor_job(_read_file)
            
            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                data.add_field(
                    'file',
                    file_data,
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
            return self.data if self.data else None