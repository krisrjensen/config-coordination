"""Service registry for coordinating multiple services"""

import json
import time
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict


@dataclass
class ServiceInfo:
    """Information about a registered service"""
    name: str
    host: str
    port: int
    status: str
    service_type: str
    version: str
    health_endpoint: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    registered_at: Optional[str] = None
    last_heartbeat: Optional[str] = None


class ServiceRegistry:
    """Service registry for managing and coordinating services"""
    
    def __init__(self, registry_file: str = "service_registry.json", 
                 heartbeat_timeout: int = 300):
        self.registry_file = Path(registry_file)
        self.heartbeat_timeout = heartbeat_timeout  # seconds
        self.services = {}
        self.load_registry()
    
    def register_service(self, name: str, host: str, port: int, 
                        service_type: str, version: str = "1.0",
                        health_endpoint: Optional[str] = None,
                        metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Register a new service
        
        Args:
            name: Service name (unique identifier)
            host: Service host/IP address
            port: Service port
            service_type: Type of service (e.g., 'api', 'worker', 'database')
            version: Service version
            health_endpoint: Optional health check endpoint
            metadata: Additional service metadata
            
        Returns:
            bool: True if registered successfully
        """
        
        service_info = ServiceInfo(
            name=name,
            host=host,
            port=port,
            status="active",
            service_type=service_type,
            version=version,
            health_endpoint=health_endpoint,
            metadata=metadata or {},
            registered_at=datetime.now().isoformat(),
            last_heartbeat=datetime.now().isoformat()
        )
        
        self.services[name] = service_info
        self.save_registry()
        
        return True
    
    def unregister_service(self, name: str) -> bool:
        """Unregister a service
        
        Args:
            name: Service name
            
        Returns:
            bool: True if unregistered successfully
        """
        
        if name in self.services:
            del self.services[name]
            self.save_registry()
            return True
        
        return False
    
    def update_service_status(self, name: str, status: str) -> bool:
        """Update service status
        
        Args:
            name: Service name
            status: New status ('active', 'inactive', 'maintenance', 'error')
            
        Returns:
            bool: True if updated successfully
        """
        
        if name in self.services:
            self.services[name].status = status
            self.services[name].last_heartbeat = datetime.now().isoformat()
            self.save_registry()
            return True
        
        return False
    
    def heartbeat(self, name: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Send heartbeat for a service
        
        Args:
            name: Service name
            metadata: Optional updated metadata
            
        Returns:
            bool: True if heartbeat recorded successfully
        """
        
        if name in self.services:
            self.services[name].last_heartbeat = datetime.now().isoformat()
            if metadata:
                self.services[name].metadata.update(metadata)
            self.save_registry()
            return True
        
        return False
    
    def get_service(self, name: str) -> Optional[ServiceInfo]:
        """Get information about a specific service
        
        Args:
            name: Service name
            
        Returns:
            ServiceInfo or None: Service information if found
        """
        
        return self.services.get(name)
    
    def get_services_by_type(self, service_type: str) -> List[ServiceInfo]:
        """Get all services of a specific type
        
        Args:
            service_type: Type of service to filter by
            
        Returns:
            list: List of ServiceInfo objects
        """
        
        return [service for service in self.services.values() 
                if service.service_type == service_type]
    
    def get_active_services(self) -> List[ServiceInfo]:
        """Get all active services
        
        Returns:
            list: List of active ServiceInfo objects
        """
        
        self.cleanup_stale_services()
        return [service for service in self.services.values() 
                if service.status == "active"]
    
    def get_all_services(self) -> Dict[str, ServiceInfo]:
        """Get all registered services
        
        Returns:
            dict: Dictionary mapping service names to ServiceInfo objects
        """
        
        return self.services.copy()
    
    def cleanup_stale_services(self) -> int:
        """Remove services that haven't sent heartbeat within timeout
        
        Returns:
            int: Number of services removed
        """
        
        current_time = datetime.now()
        stale_services = []
        
        for name, service in self.services.items():
            if service.last_heartbeat:
                last_heartbeat = datetime.fromisoformat(service.last_heartbeat)
                if (current_time - last_heartbeat).total_seconds() > self.heartbeat_timeout:
                    stale_services.append(name)
        
        # Remove stale services
        for name in stale_services:
            del self.services[name]
        
        if stale_services:
            self.save_registry()
        
        return len(stale_services)
    
    def find_service(self, service_type: str, status: str = "active") -> Optional[ServiceInfo]:
        """Find first available service of given type and status
        
        Args:
            service_type: Type of service to find
            status: Required status (default: "active")
            
        Returns:
            ServiceInfo or None: First matching service
        """
        
        for service in self.services.values():
            if service.service_type == service_type and service.status == status:
                return service
        
        return None
    
    def get_service_url(self, name: str, endpoint: str = "") -> Optional[str]:
        """Get full URL for a service
        
        Args:
            name: Service name
            endpoint: Optional endpoint path
            
        Returns:
            str or None: Full service URL
        """
        
        service = self.get_service(name)
        if service:
            base_url = f"http://{service.host}:{service.port}"
            if endpoint:
                if not endpoint.startswith('/'):
                    endpoint = '/' + endpoint
                return f"{base_url}{endpoint}"
            return base_url
        
        return None
    
    def save_registry(self) -> None:
        """Save registry to file"""
        
        registry_data = {
            'services': {name: asdict(service) for name, service in self.services.items()},
            'updated_at': datetime.now().isoformat()
        }
        
        with open(self.registry_file, 'w') as f:
            json.dump(registry_data, f, indent=2)
    
    def load_registry(self) -> None:
        """Load registry from file"""
        
        if not self.registry_file.exists():
            return
        
        try:
            with open(self.registry_file, 'r') as f:
                registry_data = json.load(f)
            
            services_data = registry_data.get('services', {})
            self.services = {
                name: ServiceInfo(**service_data) 
                for name, service_data in services_data.items()
            }
        except Exception as e:
            print(f"Error loading registry: {e}")
            self.services = {}
    
    def get_registry_status(self) -> Dict[str, Any]:
        """Get overall registry status
        
        Returns:
            dict: Registry status information
        """
        
        self.cleanup_stale_services()
        
        status = {
            'total_services': len(self.services),
            'active_services': len([s for s in self.services.values() if s.status == "active"]),
            'service_types': {},
            'last_updated': datetime.now().isoformat()
        }
        
        # Count services by type
        for service in self.services.values():
            service_type = service.service_type
            if service_type not in status['service_types']:
                status['service_types'][service_type] = 0
            status['service_types'][service_type] += 1
        
        return status