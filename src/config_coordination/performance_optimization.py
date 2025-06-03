"""Performance optimization for configuration coordination service"""

import time
import json
import threading
from typing import Dict, Any, Optional, List, Set
from datetime import datetime, timedelta
from collections import defaultdict, OrderedDict
from dataclasses import dataclass, asdict
import weakref
import hashlib

from .file_config import FileConfigManager


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    value: Any
    timestamp: float
    access_count: int
    size_bytes: int


class OptimizedConfigCache:
    """High-performance configuration cache with intelligent eviction"""
    
    def __init__(self, max_memory_mb: int = 100, max_entries: int = 1000):
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.max_entries = max_entries
        self.cache: Dict[str, CacheEntry] = OrderedDict()
        self.memory_usage = 0
        self.lock = threading.RLock()
        
        # Statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'memory_evictions': 0
        }
    
    def _calculate_size(self, value: Any) -> int:
        """Estimate memory size of value in bytes"""
        try:
            return len(json.dumps(value, default=str).encode('utf-8'))
        except:
            return 1024  # Default estimate
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                entry.access_count += 1
                
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                
                self.stats['hits'] += 1
                return entry.value
            
            self.stats['misses'] += 1
            return None
    
    def put(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Put value in cache"""
        with self.lock:
            size_bytes = self._calculate_size(value)
            
            # Remove existing entry if present
            if key in self.cache:
                old_entry = self.cache[key]
                self.memory_usage -= old_entry.size_bytes
                del self.cache[key]
            
            # Check if we need to evict
            while (len(self.cache) >= self.max_entries or 
                   self.memory_usage + size_bytes > self.max_memory_bytes):
                if not self.cache:
                    break
                self._evict_lru()
            
            # Add new entry
            entry = CacheEntry(
                value=value,
                timestamp=time.time(),
                access_count=1,
                size_bytes=size_bytes
            )
            
            self.cache[key] = entry
            self.memory_usage += size_bytes
    
    def _evict_lru(self) -> None:
        """Evict least recently used entry"""
        if not self.cache:
            return
        
        # Remove from beginning (least recently used)
        key, entry = self.cache.popitem(last=False)
        self.memory_usage -= entry.size_bytes
        self.stats['evictions'] += 1
    
    def clear(self) -> None:
        """Clear all cache entries"""
        with self.lock:
            self.cache.clear()
            self.memory_usage = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        with self.lock:
            hit_rate = self.stats['hits'] / max(self.stats['hits'] + self.stats['misses'], 1)
            
            return {
                'entries': len(self.cache),
                'max_entries': self.max_entries,
                'memory_usage_mb': self.memory_usage / 1024 / 1024,
                'max_memory_mb': self.max_memory_bytes / 1024 / 1024,
                'hit_rate': hit_rate,
                'total_hits': self.stats['hits'],
                'total_misses': self.stats['misses'],
                'evictions': self.stats['evictions']
            }


class ConfigurationPool:
    """Object pool for configuration instances to reduce memory allocation"""
    
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self.pool: List[Dict[str, Any]] = []
        self.lock = threading.Lock()
    
    def get_config_dict(self) -> Dict[str, Any]:
        """Get a reusable configuration dictionary"""
        with self.lock:
            if self.pool:
                return self.pool.pop()
            return {}
    
    def return_config_dict(self, config_dict: Dict[str, Any]) -> None:
        """Return configuration dictionary to pool"""
        with self.lock:
            if len(self.pool) < self.max_size:
                config_dict.clear()
                self.pool.append(config_dict)


class BatchConfigOperations:
    """Batch operations for improved performance"""
    
    def __init__(self, config_manager: FileConfigManager):
        self.config_manager = config_manager
        self.batch_cache = {}
        self.batch_size = 0
    
    def add_to_batch(self, operation: str, config_name: str, 
                    config_data: Optional[Dict[str, Any]] = None) -> None:
        """Add operation to batch"""
        if operation not in self.batch_cache:
            self.batch_cache[operation] = []
        
        self.batch_cache[operation].append({
            'config_name': config_name,
            'config_data': config_data,
            'timestamp': time.time()
        })
        self.batch_size += 1
    
    def execute_batch(self) -> Dict[str, Any]:
        """Execute all batched operations"""
        start_time = time.time()
        results = {
            'operations_executed': 0,
            'errors': [],
            'execution_time': 0
        }
        
        try:
            # Execute save operations
            if 'save' in self.batch_cache:
                for op in self.batch_cache['save']:
                    try:
                        self.config_manager.save_config(
                            op['config_name'], 
                            op['config_data']
                        )
                        results['operations_executed'] += 1
                    except Exception as e:
                        results['errors'].append(f"Save {op['config_name']}: {e}")
            
            # Execute load operations
            if 'load' in self.batch_cache:
                loaded_configs = {}
                for op in self.batch_cache['load']:
                    try:
                        config = self.config_manager.load_config(op['config_name'])
                        loaded_configs[op['config_name']] = config
                        results['operations_executed'] += 1
                    except Exception as e:
                        results['errors'].append(f"Load {op['config_name']}: {e}")
                
                results['loaded_configs'] = loaded_configs
            
        finally:
            results['execution_time'] = time.time() - start_time
            self.clear_batch()
        
        return results
    
    def clear_batch(self) -> None:
        """Clear batch operations"""
        self.batch_cache.clear()
        self.batch_size = 0


class OptimizedFileConfigManager(FileConfigManager):
    """Performance-optimized version of FileConfigManager"""
    
    def __init__(self, config_dir: str = "config", default_format: str = "json"):
        super().__init__(config_dir, default_format)
        self.optimized_cache = OptimizedConfigCache()
        self.config_pool = ConfigurationPool()
        self.file_watchers: Dict[str, float] = {}  # filename -> last_modified
        self.compression_enabled = False
        
        # Performance metrics
        self.metrics = {
            'load_times': [],
            'save_times': [],
            'cache_usage': defaultdict(int)
        }
    
    def enable_compression(self, enable: bool = True) -> None:
        """Enable/disable configuration compression"""
        self.compression_enabled = enable
    
    def load_config(self, config_name: str, use_cache: bool = True) -> Dict[str, Any]:
        """Optimized configuration loading with caching"""
        start_time = time.time()
        
        cache_key = f"config:{config_name}"
        
        # Try cache first
        if use_cache:
            cached_config = self.optimized_cache.get(cache_key)
            if cached_config is not None:
                self.metrics['cache_usage']['hits'] += 1
                return cached_config
        
        # Load from file
        config_data = super().load_config(config_name, use_cache=False)
        
        # Cache the result
        if use_cache:
            self.optimized_cache.put(cache_key, config_data)
            self.metrics['cache_usage']['misses'] += 1
        
        # Record performance metric
        load_time = time.time() - start_time
        self.metrics['load_times'].append(load_time)
        if len(self.metrics['load_times']) > 1000:
            self.metrics['load_times'].pop(0)
        
        return config_data
    
    def save_config(self, config_name: str, config_data: Dict[str, Any], 
                   format: Optional[str] = None) -> str:
        """Optimized configuration saving"""
        start_time = time.time()
        
        # Use pooled dictionary if possible
        if isinstance(config_data, dict):
            optimized_data = self.config_pool.get_config_dict()
            optimized_data.update(config_data)
        else:
            optimized_data = config_data
        
        try:
            # Save using parent method
            filepath = super().save_config(config_name, optimized_data, format)
            
            # Update cache
            cache_key = f"config:{config_name}"
            self.optimized_cache.put(cache_key, optimized_data.copy())
            
            # Record performance metric
            save_time = time.time() - start_time
            self.metrics['save_times'].append(save_time)
            if len(self.metrics['save_times']) > 1000:
                self.metrics['save_times'].pop(0)
            
            return filepath
            
        finally:
            # Return dictionary to pool
            if optimized_data is not config_data:
                self.config_pool.return_config_dict(optimized_data)
    
    def bulk_load_configs(self, config_names: List[str]) -> Dict[str, Dict[str, Any]]:
        """Load multiple configurations efficiently"""
        batch_ops = BatchConfigOperations(self)
        
        for config_name in config_names:
            batch_ops.add_to_batch('load', config_name)
        
        results = batch_ops.execute_batch()
        return results.get('loaded_configs', {})
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics"""
        load_times = self.metrics['load_times']
        save_times = self.metrics['save_times']
        
        stats = {
            'cache_stats': self.optimized_cache.get_stats(),
            'load_performance': {
                'total_loads': len(load_times),
                'average_time': sum(load_times) / max(len(load_times), 1),
                'min_time': min(load_times) if load_times else 0,
                'max_time': max(load_times) if load_times else 0
            },
            'save_performance': {
                'total_saves': len(save_times),
                'average_time': sum(save_times) / max(len(save_times), 1),
                'min_time': min(save_times) if save_times else 0,
                'max_time': max(save_times) if save_times else 0
            },
            'cache_usage': dict(self.metrics['cache_usage']),
            'pool_stats': {
                'pool_size': len(self.config_pool.pool),
                'max_pool_size': self.config_pool.max_size
            }
        }
        
        return stats
    
    def optimize_for_read_heavy(self) -> None:
        """Optimize settings for read-heavy workloads"""
        self.optimized_cache = OptimizedConfigCache(max_memory_mb=200, max_entries=2000)
        self.config_pool.max_size = 200
    
    def optimize_for_write_heavy(self) -> None:
        """Optimize settings for write-heavy workloads"""
        self.optimized_cache = OptimizedConfigCache(max_memory_mb=50, max_entries=500)
        self.config_pool.max_size = 50
        self.enable_compression(True)
    
    def cleanup_performance_data(self) -> None:
        """Clean up old performance data to prevent memory leaks"""
        # Keep only recent metrics
        max_metrics = 500
        if len(self.metrics['load_times']) > max_metrics:
            self.metrics['load_times'] = self.metrics['load_times'][-max_metrics:]
        if len(self.metrics['save_times']) > max_metrics:
            self.metrics['save_times'] = self.metrics['save_times'][-max_metrics:]
        
        # Reset cache usage counters periodically
        total_operations = sum(self.metrics['cache_usage'].values())
        if total_operations > 10000:
            self.metrics['cache_usage'].clear()


class PerformanceProfiler:
    """Profiler for monitoring configuration service performance"""
    
    def __init__(self):
        self.operation_times: Dict[str, List[float]] = defaultdict(list)
        self.memory_snapshots: List[Dict[str, Any]] = []
        self.start_time = time.time()
    
    def profile_operation(self, operation_name: str):
        """Decorator for profiling operations"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    end_time = time.time()
                    execution_time = end_time - start_time
                    self.operation_times[operation_name].append(execution_time)
                    
                    # Keep only recent measurements
                    if len(self.operation_times[operation_name]) > 1000:
                        self.operation_times[operation_name].pop(0)
            
            return wrapper
        return decorator
    
    def take_memory_snapshot(self) -> None:
        """Take a memory usage snapshot"""
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            
            snapshot = {
                'timestamp': time.time(),
                'rss_mb': memory_info.rss / 1024 / 1024,
                'vms_mb': memory_info.vms / 1024 / 1024
            }
            
            self.memory_snapshots.append(snapshot)
            
            # Keep only recent snapshots
            if len(self.memory_snapshots) > 100:
                self.memory_snapshots.pop(0)
                
        except ImportError:
            pass  # psutil not available
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        report = {
            'uptime_seconds': time.time() - self.start_time,
            'operations': {},
            'memory_usage': {
                'snapshots_available': len(self.memory_snapshots),
                'current_snapshot': self.memory_snapshots[-1] if self.memory_snapshots else None
            }
        }
        
        # Analyze operation performance
        for operation, times in self.operation_times.items():
            if times:
                report['operations'][operation] = {
                    'total_calls': len(times),
                    'average_time': sum(times) / len(times),
                    'min_time': min(times),
                    'max_time': max(times),
                    'p95_time': sorted(times)[int(len(times) * 0.95)] if len(times) >= 20 else max(times)
                }
        
        return report