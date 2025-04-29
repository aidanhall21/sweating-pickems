from typing import Dict, List
import math
from bitarray import bitarray
import zlib
import redis
import json
import os
import time
import gzip
import numpy as np
from redis_helper import RedisHelper

class PropBitmap:
    def __init__(self, num_sims: int):
        """Initialize bitmap storage for props.
        
        Args:
            num_sims: Number of simulations run
        """
        self.num_sims = num_sims
        self.props: Dict[str, List[int]] = {}
        self.redis = RedisHelper.get_instance()
        
        # Initialize Redis connection
        redis_host = os.getenv('REDIS_HOST', '127.0.0.1')
        redis_port = int(os.getenv('REDIS_PORT', 6379))
        redis_password = os.getenv('REDIS_PASSWORD', '')
        redis_db = int(os.getenv('REDIS_DB', 0))
        
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            db=redis_db,
            decode_responses=False
        )
        
    def add_prop(self, prop_name: str, results: List[bool]) -> None:
        """Add a new prop's results as a bitmap.
        
        Args:
            prop_name: Name of the prop (e.g. "trout_1_hit")
            results: List of boolean results from simulations
        """
        if len(results) != self.num_sims:
            raise ValueError(f"Expected {self.num_sims} results, got {len(results)}")
            
        # Convert results to bytes
        binary_data = bytearray([0] * ((self.num_sims + 7) // 8))
        for i, result in enumerate(results):
            if result:
                binary_data[i // 8] |= 1 << (i % 8)
        
        # Compress the data
        compressed = gzip.compress(bytes(binary_data))
        # Store as list of integers for JSON serialization
        self.props[prop_name] = [b for b in compressed]
        
    def get_prob(self, prop_name: str) -> float:
        """Get probability of a prop hitting.
        
        Args:
            prop_name: Name of the prop
            
        Returns:
            Probability as float between 0 and 1
        """
        if prop_name not in self.props:
            return None
        
        # Decompress the data
        compressed = bytes(self.props[prop_name])
        binary_data = gzip.decompress(compressed)
        
        # Count the ones
        count = 0
        for i in range(self.num_sims):
            if binary_data[i // 8] & (1 << (i % 8)):
                count += 1
        
        return count / self.num_sims
        
    def get_joint_prob(self, prop1: str, prop2: str) -> float:
        """Get probability of both props hitting.
        
        Args:
            prop1: First prop name
            prop2: Second prop name
            
        Returns:
            Joint probability as float between 0 and 1
        """
        if prop1 not in self.props or prop2 not in self.props:
            raise KeyError("Props not found")
            
        # Bitwise AND is very efficient with bitarray
        joint_bits = self.props[prop1] & self.props[prop2]
        return joint_bits.count(1) / self.num_sims
        
    def get_correlation(self, prop1: str, prop2: str) -> float:
        """Calculate correlation between two props.
        
        Args:
            prop1: First prop name
            prop2: Second prop name
            
        Returns:
            Correlation coefficient between -1 and 1
        """
        p1 = self.get_prob(prop1)
        p2 = self.get_prob(prop2)
        p_joint = self.get_joint_prob(prop1, prop2)
        
        # Calculate correlation coefficient
        numerator = p_joint - (p1 * p2)
        denominator = math.sqrt(p1 * (1-p1) * p2 * (1-p2))
        
        if denominator == 0:
            return 0
        return numerator / denominator
        
    def get_prop_results(self, prop_name: str) -> List[bool]:
        """Get boolean array of results for a prop.
        
        Args:
            prop_name: Name of the prop
            
        Returns:
            List of booleans of length num_sims
        """
        if prop_name not in self.props:
            raise KeyError(f"No prop named {prop_name}")
            
        return [bool(self.props[prop_name][i // 8] & (1 << (i % 8))) for i in range(self.num_sims)]
        
    def to_json(self) -> Dict:
        """Convert bitmap storage to JSON-serializable format with compression.
        
        Returns:
            Dictionary containing compressed props data
        """
        return {
            'num_sims': self.num_sims,
            'props': self.props
        }
    
    @classmethod
    def from_json(cls, data: Dict) -> 'PropBitmap':
        """Create PropBitmap from JSON data.
        
        Args:
            data: Dictionary containing compressed props data
            
        Returns:
            PropBitmap instance
        """
        if isinstance(data, str):
            data = json.loads(data)
        
        instance = cls(data['num_sims'])
        instance.props = data['props']
        return instance

    def visualize_prop(self, prop_name: str) -> Dict:
        """Visualize the bitmap results for a prop in a readable format.
        
        Args:
            prop_name: Name of the prop
            
        Returns:
            Dictionary containing visualization data
        """
        if prop_name not in self.props:
            raise KeyError(f"No prop named {prop_name}")
            
        bits = self.props[prop_name]
        hit_indices = [i for i, hit in enumerate(bits) if hit]
        prob = self.get_prob(prop_name)
        
        # Create summary
        hits = len(hit_indices)
        summary = (
            f"Prop: {prop_name}\n"
            f"Hit in {hits} out of {self.num_sims} simulations ({prob:.3%})\n"
            f"First 10 hits occurred in simulations: {hit_indices[:10]}"
        )
        
        # For large numbers of simulations, group hits by ranges
        hit_ranges = []
        current_range = []
        for i in hit_indices:
            if not current_range or i == current_range[-1] + 1:
                current_range.append(i)
            else:
                if len(current_range) > 1:
                    hit_ranges.append(f"{current_range[0]}-{current_range[-1]}")
                else:
                    hit_ranges.append(str(current_range[0]))
                current_range = [i]
                
        if current_range:
            if len(current_range) > 1:
                hit_ranges.append(f"{current_range[0]}-{current_range[-1]}")
            else:
                hit_ranges.append(str(current_range[0]))
        
        return {
            'hit_indices': hit_indices,
            'hit_ranges': hit_ranges,
            'probability': prob,
            'summary': summary,
            'compressed_size': len(gzip.compress(bytes(bits)))
        }

    def visualize_props_for_player(self, player_name: str) -> Dict[str, Dict]:
        """Visualize all props for a given player.
        
        Args:
            player_name: Name of the player
            
        Returns:
            Dictionary mapping prop names to their visualizations
        """
        player_props = {
            name: self.visualize_prop(name)
            for name in self.props.keys()
            if name.startswith(player_name.lower())
        }
        
        if not player_props:
            raise KeyError(f"No props found for player {player_name}")
            
        return player_props 

    def save_to_redis(self, key_prefix: str = 'pickem_sim_') -> None:
        """Save bitmap data to Redis with compression.
        
        Args:
            key_prefix: Prefix for Redis keys
        """
        # Generate unique key prefix with timestamp
        timestamp = math.floor(time.time())
        unique_prefix = f"{key_prefix}{timestamp}_"
        
        # Clear old simulation data
        old_keys = self.redis_client.keys(f"{key_prefix}*")
        if old_keys:
            self.redis_client.delete(*old_keys)
        
        # Store metadata
        meta_key = f"{unique_prefix}metadata"
        metadata = {
            'num_sims': self.num_sims,
            'timestamp': timestamp
        }
        self.redis_client.set(meta_key, json.dumps(metadata), ex=86400)  # 24 hour TTL
        
        # Store each prop's bitmap with compression
        for name, bits in self.props.items():
            prop_key = f"{unique_prefix}prop_{name}"
            compressed = gzip.compress(bytes(bits))
            self.redis_client.set(prop_key, compressed, ex=86400)  # 24 hour TTL
            
    @classmethod
    def load_from_redis(cls, key_prefix: str = 'pickem_sim_') -> 'PropBitmap':
        """Load bitmap data from Redis.
        
        Args:
            key_prefix: Prefix for Redis keys
            
        Returns:
            PropBitmap instance with loaded data
        """
        redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', '127.0.0.1'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            password=os.getenv('REDIS_PASSWORD', ''),
            db=int(os.getenv('REDIS_DB', 0)),
            decode_responses=False
        )
        
        # Find the most recent metadata key
        metadata_keys = redis_client.keys(f"{key_prefix}*metadata")
        if not metadata_keys:
            raise KeyError("No simulation data found in Redis")
            
        # Sort keys by timestamp (newest first)
        metadata_keys.sort(reverse=True)
        latest_meta_key = metadata_keys[0]
        
        # Extract the unique prefix from the metadata key
        unique_prefix = latest_meta_key.decode('utf-8').replace('metadata', '')
        
        # Load metadata
        meta_data = redis_client.get(latest_meta_key)
        if not meta_data:
            raise KeyError("No simulation data found in Redis")
            
        metadata = json.loads(meta_data)
        instance = cls(metadata['num_sims'])
        instance.redis_client = redis_client
        
        # Load all props with the unique prefix
        for key in redis_client.keys(f"{unique_prefix}prop_*"):
            compressed_data = redis_client.get(key)
            if compressed_data:
                prop_name = key.decode('utf-8').replace(f"{unique_prefix}prop_", "")
                decompressed = gzip.decompress(compressed_data)
                instance.props[prop_name] = [b for b in decompressed]
                
        return instance 