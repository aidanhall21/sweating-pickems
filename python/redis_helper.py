import redis
import json
import pickle
import time
import logging

class RedisHelper:
    _instance = None
    REDIS_PREFIX = 'pickem_'  # Match PHP prefix

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.redis = redis.Redis(
            host='127.0.0.1',
            port=6379,
            db=0,
            password='Blurred-Similarly-Jailhouse4-Casket',  # Add your Redis password here
            decode_responses=False,  # We want binary for bitmap data
            socket_timeout=30,  # Increase socket timeout
            socket_connect_timeout=10,  # Add connection timeout
            retry_on_timeout=True  # Enable retry on timeout
        )
        # Test the connection
        try:
            self.redis.ping()
        except redis.ConnectionError as e:
            self.logger.error(f"Failed to connect to Redis: {str(e)}")
            raise

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
        
        # Add retry logic for large data writes
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                return self.redis.set(key, value, ex=ttl)
            except redis.exceptions.ConnectionError as e:
                if attempt == max_retries - 1:  # Last attempt
                    raise
                time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
            except Exception as e:
                raise

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

    def get_player_bitmap(self, player_name):
        """Get player's bitmap data from Redis, reconstructing from chunks if necessary"""
        try:
            # First check if we have chunked data
            metadata_key = f'pickem_player_bitmap_{player_name}_metadata'
            metadata = self.get(metadata_key)
            
            if metadata:
                # We have chunked data, reconstruct it
                all_props = {}
                for i in range(metadata['num_chunks']):
                    chunk_key = f'pickem_player_bitmap_{player_name}_chunk_{i}'
                    chunk_data = self.get(chunk_key)
                    if chunk_data:
                        all_props.update(chunk_data)
                return all_props
            else:
                # Try to get non-chunked data (for backward compatibility)
                return self.get(f'pickem_player_bitmap_{player_name}')
        except Exception as e:
            self.logger.error(f'Error getting player bitmap data for {player_name}: {str(e)}')
            return None 