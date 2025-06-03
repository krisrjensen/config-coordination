"""API extensions for configuration coordination service"""

import json
import time
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path

from .config_service import ConfigService
from .advanced_config import AdvancedConfigManager


@dataclass
class ConfigSubscription:
    """Configuration change subscription"""
    subscriber_id: str
    config_patterns: List[str]
    callback_url: Optional[str]
    callback_function: Optional[Callable]
    created_at: str
    last_notified: str


class ConfigCoordinationAPI:
    """Extended API for configuration coordination with advanced features"""
    
    def __init__(self, config_dir: str = "config", registry_file: str = "service_registry.json"):
        self.advanced_config = AdvancedConfigManager(config_dir)
        self.base_service = ConfigService(config_dir, registry_file)
        self.subscriptions: Dict[str, ConfigSubscription] = {}
        self.change_log: List[Dict[str, Any]] = []
        
    # Enhanced Configuration Management
    def create_configuration_schema(self, schema_name: str, 
                                  schema_definition: Dict[str, Any]) -> str:
        """Create a configuration schema for validation
        
        Args:
            schema_name: Name of the schema
            schema_definition: JSON schema definition
            
        Returns:
            str: Path to saved schema file
        """
        schema_data = {
            "schema_name": schema_name,
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "schema": schema_definition
        }
        
        return self.advanced_config.save_config(f"schema_{schema_name}", schema_data)
    
    def validate_configuration(self, config_name: str, schema_name: str) -> Dict[str, Any]:
        """Validate configuration against a schema
        
        Args:
            config_name: Name of configuration to validate
            schema_name: Name of schema to validate against
            
        Returns:
            dict: Validation results
        """
        try:
            config_data = self.advanced_config.load_config(config_name)
            schema_data = self.advanced_config.load_config(f"schema_{schema_name}")
            
            self.advanced_config._validate_config_schema(config_data, schema_data["schema"])
            
            return {
                "valid": True,
                "config_name": config_name,
                "schema_name": schema_name,
                "validated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "valid": False,
                "config_name": config_name,
                "schema_name": schema_name,
                "error": str(e),
                "validated_at": datetime.now().isoformat()
            }
    
    def create_configuration_environment(self, env_name: str, 
                                       base_configs: List[str]) -> str:
        """Create a configuration environment from multiple base configs
        
        Args:
            env_name: Name of environment
            base_configs: List of base configuration names
            
        Returns:
            str: Path to environment configuration
        """
        env_config = {
            "environment_name": env_name,
            "created_at": datetime.now().isoformat(),
            "base_configurations": base_configs,
            "overrides": {},
            "active": True
        }
        
        # Merge all base configurations
        merged_config_name = f"env_{env_name}_merged"
        self.advanced_config.merge_configs(base_configs, merged_config_name, "deep_merge")
        
        env_config["merged_config"] = merged_config_name
        
        return self.advanced_config.save_config(f"environment_{env_name}", env_config)
    
    def apply_environment_override(self, env_name: str, 
                                 override_key: str, override_value: Any) -> str:
        """Apply override to environment configuration
        
        Args:
            env_name: Environment name
            override_key: Configuration key to override
            override_value: New value for the key
            
        Returns:
            str: Path to updated environment configuration
        """
        env_config = self.advanced_config.load_config(f"environment_{env_name}")
        env_config["overrides"][override_key] = override_value
        env_config["last_modified"] = datetime.now().isoformat()
        
        return self.advanced_config.save_config(f"environment_{env_name}", env_config)
    
    # Service Coordination Extensions
    def register_service_with_config(self, service_name: str, host: str, port: int,
                                   service_type: str, config_template: str,
                                   version: str = "1.0") -> Dict[str, Any]:
        """Register service with automatic configuration setup
        
        Args:
            service_name: Name of service
            host: Service host
            port: Service port
            service_type: Type of service
            config_template: Configuration template to use
            version: Service version
            
        Returns:
            dict: Registration result with configuration info
        """
        # Register service
        registration_result = self.base_service.register_service(
            service_name, host, port, service_type, version
        )
        
        if registration_result:
            # Create service configuration from template
            try:
                template_config = self.advanced_config.load_config(f"template_{config_template}")
                service_config = template_config.copy()
                
                # Remove template metadata
                service_config.pop("_template", None)
                service_config.pop("_template_info", None)
                
                # Add service-specific metadata
                service_config["service_name"] = service_name
                service_config["service_type"] = service_type
                service_config["host"] = host
                service_config["port"] = port
                service_config["configured_at"] = datetime.now().isoformat()
                
                config_path = self.advanced_config.save_config(f"service_{service_name}", service_config)
                
                return {
                    "success": True,
                    "service_name": service_name,
                    "config_path": config_path,
                    "template_used": config_template
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "service_name": service_name,
                    "error": f"Failed to create configuration: {e}"
                }
        
        return {"success": False, "error": "Service registration failed"}
    
    def get_service_health_status(self, service_name: str) -> Dict[str, Any]:
        """Get comprehensive health status for a service
        
        Args:
            service_name: Name of service
            
        Returns:
            dict: Comprehensive health status
        """
        service = self.base_service.get_service(service_name)
        if not service:
            return {"error": f"Service '{service_name}' not found"}
        
        # Get service configuration
        try:
            service_config = self.advanced_config.load_config(f"service_{service_name}")
        except FileNotFoundError:
            service_config = {}
        
        # Calculate uptime
        if service.registered_at:
            registered_time = datetime.fromisoformat(service.registered_at)
            uptime_seconds = (datetime.now() - registered_time).total_seconds()
        else:
            uptime_seconds = 0
        
        # Calculate last heartbeat age
        if service.last_heartbeat:
            last_heartbeat = datetime.fromisoformat(service.last_heartbeat)
            heartbeat_age = (datetime.now() - last_heartbeat).total_seconds()
        else:
            heartbeat_age = float('inf')
        
        # Determine health status
        if heartbeat_age > 300:  # 5 minutes
            health_status = "unhealthy"
        elif heartbeat_age > 120:  # 2 minutes
            health_status = "warning"
        else:
            health_status = "healthy"
        
        return {
            "service_name": service_name,
            "health_status": health_status,
            "uptime_seconds": uptime_seconds,
            "last_heartbeat_age": heartbeat_age,
            "service_info": asdict(service),
            "configuration": service_config,
            "checked_at": datetime.now().isoformat()
        }
    
    # Configuration Change Management
    def subscribe_to_config_changes(self, subscriber_id: str, 
                                  config_patterns: List[str],
                                  callback_function: Optional[Callable] = None,
                                  callback_url: Optional[str] = None) -> bool:
        """Subscribe to configuration changes
        
        Args:
            subscriber_id: Unique identifier for subscriber
            config_patterns: List of configuration name patterns to watch
            callback_function: Function to call on changes
            callback_url: URL to POST changes to
            
        Returns:
            bool: True if subscription created successfully
        """
        subscription = ConfigSubscription(
            subscriber_id=subscriber_id,
            config_patterns=config_patterns,
            callback_url=callback_url,
            callback_function=callback_function,
            created_at=datetime.now().isoformat(),
            last_notified=datetime.now().isoformat()
        )
        
        self.subscriptions[subscriber_id] = subscription
        
        # Set up watchers for each pattern
        for pattern in config_patterns:
            try:
                self.advanced_config.watch_config(pattern, self._notify_subscribers)
            except FileNotFoundError:
                pass  # Config doesn't exist yet
        
        return True
    
    def _notify_subscribers(self, config_name: str, config_data: Dict[str, Any]) -> None:
        """Notify subscribers of configuration changes"""
        change_event = {
            "config_name": config_name,
            "changed_at": datetime.now().isoformat(),
            "change_type": "modified"
        }
        
        self.change_log.append(change_event)
        
        # Notify matching subscribers
        for subscriber_id, subscription in self.subscriptions.items():
            if self._matches_patterns(config_name, subscription.config_patterns):
                if subscription.callback_function:
                    try:
                        subscription.callback_function(config_name, config_data)
                    except Exception as e:
                        print(f"Error calling subscriber callback: {e}")
                
                subscription.last_notified = datetime.now().isoformat()
    
    def _matches_patterns(self, config_name: str, patterns: List[str]) -> bool:
        """Check if config name matches any pattern"""
        import fnmatch
        return any(fnmatch.fnmatch(config_name, pattern) for pattern in patterns)
    
    def get_configuration_changelog(self, config_name: Optional[str] = None,
                                  since: Optional[str] = None,
                                  limit: int = 100) -> List[Dict[str, Any]]:
        """Get configuration change log
        
        Args:
            config_name: Optional config name filter
            since: Optional timestamp to filter changes since
            limit: Maximum number of changes to return
            
        Returns:
            list: List of change events
        """
        changes = self.change_log.copy()
        
        # Filter by config name
        if config_name:
            changes = [c for c in changes if c["config_name"] == config_name]
        
        # Filter by timestamp
        if since:
            since_dt = datetime.fromisoformat(since)
            changes = [c for c in changes if datetime.fromisoformat(c["changed_at"]) > since_dt]
        
        # Sort by timestamp (newest first) and limit
        changes.sort(key=lambda x: x["changed_at"], reverse=True)
        return changes[:limit]
    
    def create_configuration_backup(self, backup_name: str,
                                  config_patterns: Optional[List[str]] = None) -> str:
        """Create backup of configurations
        
        Args:
            backup_name: Name for backup
            config_patterns: Optional patterns to filter configs
            
        Returns:
            str: Path to backup file
        """
        backup_data = {
            "backup_name": backup_name,
            "created_at": datetime.now().isoformat(),
            "configurations": {},
            "service_registry": self.base_service.service_registry.get_all_services()
        }
        
        # Include all or filtered configurations
        all_configs = self.advanced_config.list_configs()
        
        if config_patterns:
            import fnmatch
            filtered_configs = []
            for config in all_configs:
                if any(fnmatch.fnmatch(config, pattern) for pattern in config_patterns):
                    filtered_configs.append(config)
            all_configs = filtered_configs
        
        for config_name in all_configs:
            try:
                config_data = self.advanced_config.load_config(config_name)
                backup_data["configurations"][config_name] = config_data
            except Exception as e:
                backup_data["configurations"][config_name] = {"error": str(e)}
        
        backup_path = self.advanced_config.save_config(f"backup_{backup_name}", backup_data)
        return backup_path
    
    def restore_configuration_backup(self, backup_name: str,
                                   selective_restore: Optional[List[str]] = None) -> Dict[str, Any]:
        """Restore configurations from backup
        
        Args:
            backup_name: Name of backup to restore
            selective_restore: Optional list of specific configs to restore
            
        Returns:
            dict: Restoration results
        """
        try:
            backup_data = self.advanced_config.load_config(f"backup_{backup_name}")
            
            restored_configs = []
            errors = []
            
            configurations = backup_data.get("configurations", {})
            
            for config_name, config_data in configurations.items():
                if selective_restore and config_name not in selective_restore:
                    continue
                
                if "error" in config_data:
                    errors.append(f"{config_name}: {config_data['error']}")
                    continue
                
                try:
                    self.advanced_config.save_config(config_name, config_data)
                    restored_configs.append(config_name)
                except Exception as e:
                    errors.append(f"{config_name}: {str(e)}")
            
            return {
                "success": True,
                "backup_name": backup_name,
                "restored_configs": restored_configs,
                "errors": errors,
                "restored_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "success": False,
                "backup_name": backup_name,
                "error": str(e)
            }