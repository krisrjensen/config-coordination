"""Configuration Coordination Service"""

from .config_service import ConfigService
from .service_registry import ServiceRegistry
from .file_config import FileConfigManager

__version__ = "20250602_000000_0_1_0_2"
__all__ = ["ConfigService", "ServiceRegistry", "FileConfigManager"]

# Advanced features
try:
    from .advanced_config import AdvancedConfigManager
    from .api_extensions import ConfigCoordinationAPI
    from .performance_optimization import OptimizedFileConfigManager
    __all__.extend(["AdvancedConfigManager", "ConfigCoordinationAPI", "OptimizedFileConfigManager"])
except ImportError:
    pass