"""Configuration Coordination Service"""

from .config_service import ConfigService
from .service_registry import ServiceRegistry
from .file_config import FileConfigManager

__version__ = "20250602_000000_0_1_0_1"
__all__ = ["ConfigService", "ServiceRegistry", "FileConfigManager"]