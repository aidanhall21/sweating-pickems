import redis
import json
import pickle

class RedisHelper:
    _instance = None
    REDIS_PREFIX = 'pickem_'  # Match PHP prefix

    def __init__(self):
        self.redis = redis.Redis(
            host='127.0.0.1',
            port=6379,
            db=0,
            decode_responses=False  # We want binary for bitmap data
        )

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set(self, key, value, ttl=3600):  # Default 1 hour TTL to match PHP
        """Store value in Redis with optional TTL"""
        # Only add prefix if key doesn't already start with it
        if not key.startswith(self.REDIS_PREFIX):
            key = f"{self.REDIS_PREFIX}{key}"  # Add prefix to match PHP
        if isinstance(value, (dict, list)):
            value = json.dumps(value).encode('utf-8')  # Use JSON for compatibility
        return self.redis.set(key, value, ex=ttl)

    def get(self, key):
        """Get value from Redis"""
        # Only add prefix if key doesn't already start with it
        if not key.startswith(self.REDIS_PREFIX):
            key = f"{self.REDIS_PREFIX}{key}"
        value = self.redis.get(key)
        if value is None:
            return None
        try:
            return json.loads(value.decode('utf-8'))  # Try JSON decode first
        except:
            return value  # Return raw value if not JSON

    def delete(self, key):
        """Delete key from Redis"""
        # Only add prefix if key doesn't already start with it
        if not key.startswith(self.REDIS_PREFIX):
            key = f"{self.REDIS_PREFIX}{key}"
        return self.redis.delete(key)

    def exists(self, key):
        """Check if key exists in Redis"""
        # Only add prefix if key doesn't already start with it
        if not key.startswith(self.REDIS_PREFIX):
            key = f"{self.REDIS_PREFIX}{key}"
        return self.redis.exists(key) 