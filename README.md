# Config Coordination

Configuration coordination service with file-based management and service registry for rapid deployment.

## Features

- **File-Based Configuration**: JSON and YAML configuration management with caching
- **Service Registry**: Service discovery and health monitoring
- **Coordination Service**: Unified interface for configuration and service management
- **Rapid Deployment**: File-based approach for quick setup without external dependencies

## Quick Start

```python
from config_coordination import ConfigService

# Initialize coordination service
service = ConfigService()

# Save configuration
config_data = {
    "database": {
        "host": "localhost",
        "port": 5432,
        "name": "mydb"
    }
}
service.save_config("app_config", config_data)

# Register a service
service.register_service(
    name="api_server",
    host="localhost", 
    port=4080,
    service_type="api",
    version="1.0"
)

# Find services
api_service = service.find_service("api")
print(f"API available at: {service.get_service_url('api_server')}")
```

## Configuration Management

```python
from config_coordination import FileConfigManager

config_mgr = FileConfigManager("./configs")

# Save configuration (JSON or YAML)
config_mgr.save_config("database", {
    "host": "localhost",
    "port": 5432
}, format="yaml")

# Load configuration
db_config = config_mgr.load_config("database")

# Update configuration
config_mgr.update_config("database", {"port": 5433})

# List all configurations
configs = config_mgr.list_configs()
```

## Service Registry

```python
from config_coordination import ServiceRegistry

registry = ServiceRegistry()

# Register service
registry.register_service(
    name="worker_1",
    host="192.168.1.100",
    port=8001,
    service_type="worker",
    metadata={"capacity": 100, "location": "datacenter_1"}
)

# Send heartbeat
registry.heartbeat("worker_1", {"current_load": 75})

# Find services
workers = registry.get_services_by_type("worker")
active_services = registry.get_active_services()

# Cleanup stale services
removed_count = registry.cleanup_stale_services()
```

## System Status

```python
# Get comprehensive system status
status = service.get_system_status()
print(f"Active services: {status['service_registry']['active_services']}")
print(f"Total configs: {status['configurations']['total_configs']}")

# Health check
health = service.health_check()
print(f"Service status: {health['status']}")

# Export complete system state
service.export_system_state("system_backup.json")
```

## Installation

```bash
pip install config-coordination

# With development dependencies
pip install config-coordination[dev]

# With HTTP server support
pip install config-coordination[server]
```

## Version: 20250602_000000_0_1_0_1