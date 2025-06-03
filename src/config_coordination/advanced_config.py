"""Advanced configuration features and API extensions"""

import os
import json
import yaml
import hashlib
from typing import Dict, Any, List, Optional, Callable, Union
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import threading
import time

from .file_config import FileConfigManager


@dataclass
class ConfigWatcher:
    """Configuration file watcher for real-time updates"""
    config_name: str
    callback: Callable[[str, Dict[str, Any]], None]
    last_modified: float
    enabled: bool = True


class AdvancedConfigManager(FileConfigManager):
    """Enhanced configuration manager with advanced features"""
    
    def __init__(self, config_dir: str = "config", default_format: str = "json"):
        super().__init__(config_dir, default_format)
        self.watchers: List[ConfigWatcher] = []
        self.config_history: Dict[str, List[Dict[str, Any]]] = {}
        self.encrypted_configs: set = set()
        self._watch_thread = None
        self._watch_stop_event = threading.Event()
        
    def save_config_with_validation(self, config_name: str, config_data: Dict[str, Any], 
                                   schema: Optional[Dict[str, Any]] = None, 
                                   format: Optional[str] = None) -> str:
        """Save configuration with optional schema validation
        
        Args:
            config_name: Name of configuration
            config_data: Configuration data
            schema: Optional JSON schema for validation
            format: File format
            
        Returns:
            str: Path to saved configuration file
        """
        
        # Validate against schema if provided
        if schema:
            self._validate_config_schema(config_data, schema)
        
        # Store in history before saving
        self._add_to_history(config_name, config_data)
        
        return self.save_config(config_name, config_data, format)
    
    def _validate_config_schema(self, config_data: Dict[str, Any], 
                              schema: Dict[str, Any]) -> None:
        """Validate configuration against JSON schema"""
        # Simple validation - in production, use jsonschema library
        required_fields = schema.get("required", [])
        for field in required_fields:
            if field not in config_data:
                raise ValueError(f"Required field '{field}' missing from configuration")
        
        # Type validation
        properties = schema.get("properties", {})
        for field, field_schema in properties.items():
            if field in config_data:
                expected_type = field_schema.get("type")
                if expected_type and not self._check_type(config_data[field], expected_type):
                    raise ValueError(f"Field '{field}' has incorrect type")
    
    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected type"""
        type_mapping = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict
        }
        
        expected_python_type = type_mapping.get(expected_type)
        if expected_python_type:
            return isinstance(value, expected_python_type)
        return True
    
    def _add_to_history(self, config_name: str, config_data: Dict[str, Any]) -> None:
        """Add configuration to history"""
        if config_name not in self.config_history:
            self.config_history[config_name] = []
        
        history_entry = {
            "timestamp": datetime.now().isoformat(),
            "config": config_data.copy(),
            "checksum": self._calculate_checksum(config_data)
        }
        
        self.config_history[config_name].append(history_entry)
        
        # Limit history size
        max_history = 50
        if len(self.config_history[config_name]) > max_history:
            self.config_history[config_name] = self.config_history[config_name][-max_history:]
    
    def _calculate_checksum(self, config_data: Dict[str, Any]) -> str:
        """Calculate checksum for configuration data"""
        config_str = json.dumps(config_data, sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()
    
    def get_config_history(self, config_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get configuration change history
        
        Args:
            config_name: Name of configuration
            limit: Maximum number of history entries to return
            
        Returns:
            list: List of history entries
        """
        history = self.config_history.get(config_name, [])
        return history[-limit:]
    
    def restore_config_version(self, config_name: str, timestamp: str) -> str:
        """Restore configuration to a specific version
        
        Args:
            config_name: Name of configuration
            timestamp: Timestamp of version to restore
            
        Returns:
            str: Path to restored configuration file
        """
        history = self.config_history.get(config_name, [])
        
        for entry in history:
            if entry["timestamp"] == timestamp:
                return self.save_config(config_name, entry["config"])
        
        raise ValueError(f"Version with timestamp {timestamp} not found")
    
    def watch_config(self, config_name: str, 
                    callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Watch configuration file for changes
        
        Args:
            config_name: Name of configuration to watch
            callback: Function to call when config changes
        """
        config_file = self._find_config_file(config_name)
        if not config_file:
            raise FileNotFoundError(f"Configuration '{config_name}' not found")
        
        watcher = ConfigWatcher(
            config_name=config_name,
            callback=callback,
            last_modified=config_file.stat().st_mtime
        )
        
        self.watchers.append(watcher)
        
        # Start watch thread if not already running
        if self._watch_thread is None or not self._watch_thread.is_alive():
            self._start_watch_thread()
    
    def _find_config_file(self, config_name: str) -> Optional[Path]:
        """Find configuration file by name"""
        for ext in ['json', 'yaml', 'yml']:
            config_file = self.config_dir / f"{config_name}.{ext}"
            if config_file.exists():
                return config_file
        return None
    
    def _start_watch_thread(self) -> None:
        """Start the configuration watching thread"""
        self._watch_stop_event.clear()
        self._watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._watch_thread.start()
    
    def _watch_loop(self) -> None:
        """Main watching loop"""
        while not self._watch_stop_event.is_set():
            try:
                for watcher in self.watchers:
                    if not watcher.enabled:
                        continue
                    
                    config_file = self._find_config_file(watcher.config_name)
                    if config_file and config_file.exists():
                        current_mtime = config_file.stat().st_mtime
                        
                        if current_mtime > watcher.last_modified:
                            # Configuration file has changed
                            try:
                                new_config = self.load_config(watcher.config_name, use_cache=False)
                                watcher.callback(watcher.config_name, new_config)
                                watcher.last_modified = current_mtime
                            except Exception as e:
                                print(f"Error loading changed config '{watcher.config_name}': {e}")
                
                # Check every 2 seconds
                time.sleep(2)
                
            except Exception as e:
                print(f"Error in config watch loop: {e}")
                time.sleep(5)
    
    def stop_watching(self, config_name: Optional[str] = None) -> None:
        """Stop watching configurations
        
        Args:
            config_name: Specific config to stop watching, or None for all
        """
        if config_name:
            self.watchers = [w for w in self.watchers if w.config_name != config_name]
        else:
            self.watchers.clear()
            self._watch_stop_event.set()
    
    def merge_configs(self, config_names: List[str], 
                     output_name: str, strategy: str = "override") -> str:
        """Merge multiple configurations into one
        
        Args:
            config_names: List of configuration names to merge
            output_name: Name for merged configuration
            strategy: Merge strategy ('override', 'deep_merge', 'append')
            
        Returns:
            str: Path to merged configuration file
        """
        merged_config = {}
        
        for config_name in config_names:
            try:
                config = self.load_config(config_name)
                
                if strategy == "override":
                    merged_config.update(config)
                elif strategy == "deep_merge":
                    self._deep_merge(merged_config, config)
                elif strategy == "append":
                    for key, value in config.items():
                        if key in merged_config:
                            if isinstance(merged_config[key], list) and isinstance(value, list):
                                merged_config[key].extend(value)
                            else:
                                merged_config[key] = value
                        else:
                            merged_config[key] = value
                            
            except FileNotFoundError:
                print(f"Warning: Configuration '{config_name}' not found, skipping")
        
        # Add merge metadata
        merged_config.setdefault('_metadata', {})
        merged_config['_metadata']['merged_from'] = config_names
        merged_config['_metadata']['merge_strategy'] = strategy
        merged_config['_metadata']['merged_at'] = datetime.now().isoformat()
        
        return self.save_config(output_name, merged_config)
    
    def _deep_merge(self, base_dict: Dict[str, Any], update_dict: Dict[str, Any]) -> None:
        """Recursively merge dictionaries"""
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_merge(base_dict[key], value)
            else:
                base_dict[key] = value
    
    def create_config_template(self, template_name: str, 
                             fields: List[Dict[str, Any]]) -> str:
        """Create a configuration template
        
        Args:
            template_name: Name of template
            fields: List of field definitions
            
        Returns:
            str: Path to template file
        """
        template = {
            "_template": True,
            "_template_info": {
                "name": template_name,
                "created": datetime.now().isoformat(),
                "fields": fields
            }
        }
        
        # Create default values based on field types
        for field in fields:
            field_name = field["name"]
            field_type = field.get("type", "string")
            default_value = field.get("default")
            
            if default_value is not None:
                template[field_name] = default_value
            elif field_type == "string":
                template[field_name] = f"<{field_name}>"
            elif field_type == "integer":
                template[field_name] = 0
            elif field_type == "boolean":
                template[field_name] = False
            elif field_type == "array":
                template[field_name] = []
            elif field_type == "object":
                template[field_name] = {}
        
        return self.save_config(f"template_{template_name}", template)
    
    def get_config_diff(self, config_name: str, version1: str, version2: str) -> Dict[str, Any]:
        """Get differences between two configuration versions
        
        Args:
            config_name: Name of configuration
            version1: First version timestamp
            version2: Second version timestamp
            
        Returns:
            dict: Differences between versions
        """
        history = self.config_history.get(config_name, [])
        
        config1 = None
        config2 = None
        
        for entry in history:
            if entry["timestamp"] == version1:
                config1 = entry["config"]
            if entry["timestamp"] == version2:
                config2 = entry["config"]
        
        if not config1 or not config2:
            raise ValueError("One or both versions not found in history")
        
        return self._calculate_diff(config1, config2)
    
    def _calculate_diff(self, config1: Dict[str, Any], 
                       config2: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate differences between two configurations"""
        diff = {
            "added": {},
            "removed": {},
            "modified": {},
            "unchanged": {}
        }
        
        all_keys = set(config1.keys()) | set(config2.keys())
        
        for key in all_keys:
            if key not in config1:
                diff["added"][key] = config2[key]
            elif key not in config2:
                diff["removed"][key] = config1[key]
            elif config1[key] != config2[key]:
                diff["modified"][key] = {
                    "old": config1[key],
                    "new": config2[key]
                }
            else:
                diff["unchanged"][key] = config1[key]
        
        return diff