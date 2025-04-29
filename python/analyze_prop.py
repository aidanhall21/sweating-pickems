#!/usr/bin/env python3
import argparse
import json
from prop_bitmap import PropBitmap

def analyze_prop(prop_id: str, redis_key_prefix: str) -> dict:
    """Analyze a prop using stored simulation results from Redis.
    
    Args:
        prop_id: ID of the prop to analyze
        redis_key_prefix: Prefix for Redis keys
        
    Returns:
        Dictionary containing analysis results
    """
    try:
        # Load bitmap data from Redis
        bitmap = PropBitmap.load_from_redis(redis_key_prefix)
        
        # Parse prop ID to get components
        player_name, stat_type, value = prop_id.split('_', 2)
        value = float(value)
        
        # Construct prop name based on stat type
        if stat_type == 'hits':
            prop_name = f"{player_name}_hits_{int(value)}_plus"
        elif stat_type == 'strikeouts':
            prop_name = f"{player_name}_strikeouts_{int(value)}_plus"
        # Add more stat types as needed...
        else:
            raise ValueError(f"Unsupported stat type: {stat_type}")
            
        # Get probability from bitmap
        probability = bitmap.get_prob(prop_name)
        
        return {
            'success': True,
            'player': player_name.replace('_', ' '),
            'type': stat_type.title(),
            'line': value,
            'win_probability': probability,
            'ev': probability  # EV calculation will be done on frontend
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Analyze prop using Redis storage')
    parser.add_argument('--prop', required=True, help='Prop ID to analyze')
    parser.add_argument('--redis_key', default='pickem_sim_', help='Redis key prefix')
    
    args = parser.parse_args()
    result = analyze_prop(args.prop, args.redis_key)
    print(json.dumps(result)) 