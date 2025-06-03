"""Main configuration coordination service"""

import os
import time
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime

from .file_config import FileConfigManager
from .service_registry import ServiceRegistry, ServiceInfo


class ConfigService:
    """Main configuration coordination service combining file management and service registry"""
    
    def __init__(self, config_dir: str = "config", registry_file: str = "service_registry.json"):
        self.config_manager = FileConfigManager(config_dir)
        self.service_registry = ServiceRegistry(registry_file)
        self.service_name = "config-coordination"
        self.start_time = datetime.now()
        
        # Register self as a service
        self._register_self()
    
    def _register_self(self) -> None:
        """Register this configuration service in the registry"""
        
        self.service_registry.register_service(
            name=self.service_name,
            host="localhost",
            port=8080,  # Default port
            service_type="config",
            version="1.0",
            health_endpoint="/health",
            metadata={
                "config_dir": str(self.config_manager.config_dir),
                "registry_file": str(self.service_registry.registry_file),
                "capabilities": ["config_management", "service_registry", "coordination"]
            }
        )
    
    # Configuration Management Methods
    def save_config(self, config_name: str, config_data: Dict[str, Any], 
                   format: Optional[str] = None) -> str:
        """Save configuration and notify services"""
        
        filepath = self.config_manager.save_config(config_name, config_data, format)
        
        # Send heartbeat to indicate activity
        self.service_registry.heartbeat(self.service_name, {
            "last_action": "save_config",
            "config_name": config_name,
            "timestamp": datetime.now().isoformat()
        })
        
        return filepath
    
    def load_config(self, config_name: str, use_cache: bool = True) -> Dict[str, Any]:
        """Load configuration"""
        return self.config_manager.load_config(config_name, use_cache)
    
    def update_config(self, config_name: str, updates: Dict[str, Any], 
                     create_backup: bool = True) -> str:
        """Update configuration and notify services"""
        
        filepath = self.config_manager.update_config(config_name, updates, create_backup)
        
        # Notify relevant services about config update
        self._notify_config_update(config_name, updates)
        
        return filepath
    
    def delete_config(self, config_name: str, create_backup: bool = True) -> bool:
        """Delete configuration"""
        return self.config_manager.delete_config(config_name, create_backup)
    
    def list_configs(self) -> List[str]:
        """List all available configurations"""
        return self.config_manager.list_configs()
    
    # Service Registry Methods
    def register_service(self, name: str, host: str, port: int, 
                        service_type: str, version: str = "1.0",
                        health_endpoint: Optional[str] = None,
                        metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Register a service in the registry"""
        return self.service_registry.register_service(
            name, host, port, service_type, version, health_endpoint, metadata
        )
    
    def unregister_service(self, name: str) -> bool:
        """Unregister a service from the registry"""
        return self.service_registry.unregister_service(name)
    
    def get_service(self, name: str) -> Optional[ServiceInfo]:
        """Get service information"""
        return self.service_registry.get_service(name)
    
    def get_services_by_type(self, service_type: str) -> List[ServiceInfo]:
        """Get all services of a specific type"""
        return self.service_registry.get_services_by_type(service_type)
    
    def get_active_services(self) -> List[ServiceInfo]:
        """Get all active services"""
        return self.service_registry.get_active_services()
    
    def find_service(self, service_type: str, status: str = "active") -> Optional[ServiceInfo]:
        """Find first available service of given type"""
        return self.service_registry.find_service(service_type, status)
    
    def heartbeat(self, name: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Send heartbeat for a service"""
        return self.service_registry.heartbeat(name, metadata)
    
    # Coordination Methods
    def get_service_config(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific service"""
        
        try:
            return self.load_config(f"service_{service_name}")
        except FileNotFoundError:
            return None
    
    def set_service_config(self, service_name: str, config_data: Dict[str, Any]) -> str:
        """Set configuration for a specific service"""
        
        config_name = f"service_{service_name}"
        return self.save_config(config_name, config_data)
    
    def get_global_config(self) -> Dict[str, Any]:
        """Get global system configuration"""
        
        try:
            return self.load_config("global")
        except FileNotFoundError:
            # Return default global config
            return {
                "system": {
                    "name": "Data Processor System",
                    "version": "1.0",
                    "environment": "development"
                },
                "logging": {
                    "level": "INFO",
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                },
                "coordination": {
                    "heartbeat_interval": 60,
                    "cleanup_interval": 300
                }
            }
    
    def set_global_config(self, config_data: Dict[str, Any]) -> str:
        """Set global system configuration"""
        return self.save_config("global", config_data)
    
    def _notify_config_update(self, config_name: str, updates: Dict[str, Any]) -> None:
        """Notify relevant services about configuration updates"""
        
        # Find services that might be affected by this config
        if config_name.startswith("service_"):
            service_name = config_name[8:]  # Remove "service_" prefix
            service = self.get_service(service_name)
            if service:
                # Log the notification (in a real system, this would send HTTP requests)
                print(f"Config update notification for service '{service_name}': {list(updates.keys())}")
    
    def cleanup_stale_services(self) -> int:
        """Clean up stale services"""
        return self.service_registry.cleanup_stale_services()
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        
        # Clean up stale services first
        stale_count = self.cleanup_stale_services()
        
        registry_status = self.service_registry.get_registry_status()
        config_list = self.list_configs()
        
        status = {
            "config_service": {
                "name": self.service_name,
                "status": "active",
                "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
                "start_time": self.start_time.isoformat()
            },
            "configurations": {
                "total_configs": len(config_list),
                "config_names": config_list
            },
            "service_registry": registry_status,
            "cleanup": {
                "stale_services_removed": stale_count
            },
            "timestamp": datetime.now().isoformat()
        }
        
        return status
    
    def export_system_state(self, output_file: str) -> str:
        """Export complete system state (configs + registry)"""
        
        system_state = {
            "configurations": {},
            "service_registry": self.service_registry.get_all_services(),
            "system_status": self.get_system_status(),
            "export_timestamp": datetime.now().isoformat()
        }
        
        # Include all configurations
        for config_name in self.list_configs():
            try:
                system_state["configurations"][config_name] = self.load_config(config_name)
            except Exception as e:
                system_state["configurations"][config_name] = {"error": str(e)}
        
        # Save to file
        import json
        with open(output_file, 'w') as f:
            json.dump(system_state, f, indent=2, default=str)
        
        return output_file
    
    def health_check(self) -> Dict[str, Any]:
        """Health check endpoint for the configuration service"""
        
        return {
            "status": "healthy",
            "service": self.service_name,
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
            "components": {
                "config_manager": "healthy",
                "service_registry": "healthy"
            }
        }