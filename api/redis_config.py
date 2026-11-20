# redis_config.py (place this in the same directory as views.py)
import redis
from django.conf import settings
import json
import hashlib
from typing import Any, Optional
import pickle

class RedisClient:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Get Redis settings from Django settings or use defaults
            redis_host = getattr(settings, 'REDIS_HOST', 'localhost')
            redis_port = getattr(settings, 'REDIS_PORT', 6379)
            redis_db = getattr(settings, 'REDIS_DB', 0)
            redis_password = getattr(settings, 'REDIS_PASSWORD', None)
            
            cls._instance.client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password,
                decode_responses=False,
                socket_connect_timeout=2,
                socket_timeout=3,
                retry_on_timeout=True
            )
        return cls._instance
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            data = self.client.get(key)
            if data:
                return pickle.loads(data)
        except:
            return None
        return None
    
    def set(self, key: str, value: Any, timeout: int = 300) -> bool:
        """Set value in cache with timeout"""
        try:
            return self.client.setex(key, timeout, pickle.dumps(value))
        except:
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            return bool(self.client.delete(key))
        except:
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        try:
            keys = self.client.keys(pattern)
            if keys:
                return self.client.delete(*keys)
            return 0
        except:
            return 0
    
    def get_or_set(self, key: str, callback, timeout: int = 300) -> Any:
        """Get from cache or set using callback"""
        data = self.get(key)
        if data is None:
            data = callback()
            self.set(key, data, timeout)
        return data

redis_client = RedisClient()

def generate_cache_key(prefix: str, *args, **kwargs) -> str:
    """Generate consistent cache key"""
    key_parts = [prefix]
    key_parts.extend([str(arg) for arg in args if arg])
    
    if kwargs:
        sorted_items = sorted(kwargs.items())
        key_parts.extend([f"{k}:{v}" for k, v in sorted_items if v])
    
    key_string = ":".join(key_parts)
    if len(key_string) > 200:
        import hashlib
        hash_obj = hashlib.md5(key_string.encode())
        return f"{prefix}:{hash_obj.hexdigest()}"
    
    return key_string