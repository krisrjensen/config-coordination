"""File-based configuration manager for rapid deployment"""

import json
import yaml
import os
from typing import Dict, Any, Optional, Union
from pathlib import Path
from datetime import datetime


class FileConfigManager:
    """File-based configuration manager with JSON and YAML support"""
    
    def __init__(self, config_dir: str = "config", default_format: str = "json"):
        self.config_dir = Path(config_dir)
        self.default_format = default_format
        self.config_cache = {}
        self.config_dir.mkdir(exist_ok=True)
    
    def save_config(self, config_name: str, config_data: Dict[str, Any], 
                   format: Optional[str] = None) -> str:
        """Save configuration to file
        
        Args:
            config_name: Name of configuration (without extension)
            config_data: Configuration dictionary
            format: File format ('json' or 'yaml')
            
        Returns:
            str: Path to saved configuration file
        """
        
        format = format or self.default_format
        
        # Add metadata
        config_data = config_data.copy()
        config_data.setdefault('_metadata', {})
        config_data['_metadata'].update({
            'created': datetime.now().isoformat(),
            'version': "1.0",
            'format': format
        })
        
        # Determine filename
        if format == 'yaml':
            filename = f"{config_name}.yaml"
        else:
            filename = f"{config_name}.json"
        
        filepath = self.config_dir / filename
        
        # Save configuration
        with open(filepath, 'w') as f:
            if format == 'yaml':
                yaml.dump(config_data, f, default_flow_style=False, indent=2)
            else:
                json.dump(config_data, f, indent=2)
        
        # Update cache
        self.config_cache[config_name] = config_data
        
        return str(filepath)
    
    def load_config(self, config_name: str, use_cache: bool = True) -> Dict[str, Any]:
        """Load configuration from file
        
        Args:
            config_name: Name of configuration (without extension)
            use_cache: Whether to use cached version if available
            
        Returns:
            dict: Configuration data
        """
        
        # Check cache first
        if use_cache and config_name in self.config_cache:
            return self.config_cache[config_name]
        
        # Try to find config file
        config_file = None
        for ext in ['json', 'yaml', 'yml']:
            potential_file = self.config_dir / f"{config_name}.{ext}"
            if potential_file.exists():
                config_file = potential_file
                break
        
        if not config_file:
            raise FileNotFoundError(f"Configuration '{config_name}' not found in {self.config_dir}")
        
        # Load configuration
        with open(config_file, 'r') as f:
            if config_file.suffix in ['.yaml', '.yml']:
                config_data = yaml.safe_load(f)
            else:
                config_data = json.load(f)
        
        # Cache configuration
        self.config_cache[config_name] = config_data
        
        return config_data
    
    def list_configs(self) -> list:
        """List available configurations"""
        
        configs = []
        for file_path in self.config_dir.glob('*'):
            if file_path.suffix in ['.json', '.yaml', '.yml']:
                config_name = file_path.stem
                configs.append(config_name)
        
        return sorted(configs)
    
    def update_config(self, config_name: str, updates: Dict[str, Any], 
                     create_backup: bool = True) -> str:
        """Update existing configuration
        
        Args:
            config_name: Name of configuration
            updates: Dictionary of updates to apply
            create_backup: Whether to create backup before updating
            
        Returns:
            str: Path to updated configuration file
        """
        
        # Load existing configuration
        try:
            config_data = self.load_config(config_name)
        except FileNotFoundError:
            config_data = {}
        
        # Create backup if requested
        if create_backup and config_data:
            backup_name = f"{config_name}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.save_config(backup_name, config_data)
        
        # Apply updates
        config_data.update(updates)
        
        # Update metadata
        config_data.setdefault('_metadata', {})
        config_data['_metadata']['updated'] = datetime.now().isoformat()
        
        # Save updated configuration
        return self.save_config(config_name, config_data)
    
    def delete_config(self, config_name: str, create_backup: bool = True) -> bool:
        """Delete configuration file
        
        Args:
            config_name: Name of configuration
            create_backup: Whether to create backup before deleting
            
        Returns:
            bool: True if deleted successfully
        """
        
        # Create backup if requested
        if create_backup:
            try:
                config_data = self.load_config(config_name)
                backup_name = f"{config_name}_deleted_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                self.save_config(backup_name, config_data)
            except FileNotFoundError:
                pass
        
        # Find and delete config file
        for ext in ['json', 'yaml', 'yml']:
            config_file = self.config_dir / f"{config_name}.{ext}"
            if config_file.exists():
                config_file.unlink()
                # Remove from cache
                self.config_cache.pop(config_name, None)
                return True
        
        return False
    
    def get_config_info(self, config_name: str) -> Dict[str, Any]:
        """Get information about a configuration file
        
        Args:
            config_name: Name of configuration
            
        Returns:
            dict: Configuration metadata and file info
        """
        
        config_data = self.load_config(config_name)
        
        # Find config file
        config_file = None
        for ext in ['json', 'yaml', 'yml']:
            potential_file = self.config_dir / f"{config_name}.{ext}"
            if potential_file.exists():
                config_file = potential_file
                break
        
        info = {
            'name': config_name,
            'file_path': str(config_file) if config_file else None,
            'file_size': config_file.stat().st_size if config_file else None,
            'modified_time': datetime.fromtimestamp(config_file.stat().st_mtime).isoformat() if config_file else None,
            'metadata': config_data.get('_metadata', {}),
            'keys': list(config_data.keys())
        }
        
        return info
    
    def clear_cache(self) -> None:
        """Clear configuration cache"""
        self.config_cache.clear()
    
    def export_all_configs(self, output_file: str) -> str:
        """Export all configurations to a single file
        
        Args:
            output_file: Output file path
            
        Returns:
            str: Path to exported file
        """
        
        all_configs = {}
        
        for config_name in self.list_configs():
            try:
                all_configs[config_name] = self.load_config(config_name)
            except Exception as e:
                print(f"Error loading config '{config_name}': {e}")
        
        # Save all configurations
        with open(output_file, 'w') as f:
            json.dump(all_configs, f, indent=2)
        
        return output_file