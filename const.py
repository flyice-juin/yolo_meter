"""Constants for the YOLO Meter Reader integration."""
from datetime import timedelta

DOMAIN = "yolo_meter"

CONF_CAMERA_ENTITY = "camera_entity"
CONF_MODEL_TYPE = "model_type"
CONF_CROP_COORDS = "crop_coordinates"  # 新增裁剪坐标配置

DEFAULT_PORT = 4000
DEFAULT_SCAN_INTERVAL = 5  # minutes
DEFAULT_DETECT_FOLDER = "detect"
DEFAULT_BASELINE_VALUE = 0
DEFAULT_CROP_COORDS = None  # 默认不裁剪

ATTR_DETECTED_NUMBER = "detected_number"
ATTR_SUCCESS = "success"
ATTR_LAST_IMAGE = "last_image"
ATTR_LAST_UPDATE = "last_update"

# 添加中文显示名称
MODEL_TYPE_OPTIONS = {
    "digital": "电子数字仪表",
    "gas": "机械数字仪表"
}