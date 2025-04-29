<?php

class BitmapHelper {
    private $redis;
    private $metadata = null;
    private $player_list = null;
    private $player_stats = null;
    private $loaded_player_bitmaps = [];
    
    public function __construct() {
        $this->redis = new RedisHelper();
        $this->loadMetadata();
    }
    
    private function loadMetadata() {
        // Load metadata
        $metadata_json = $this->redis->get('pickem_simulation_metadata');
        if ($metadata_json) {
            $this->metadata = json_decode($metadata_json, true);
            if (!$this->metadata) {
                error_log("Failed to decode metadata JSON: " . json_last_error_msg());
            }
        } else {
            error_log("No metadata found in Redis");
        }
        
        // Load list of players
        $player_list_json = $this->redis->get('pickem_players_list');
        if ($player_list_json) {
            $this->player_list = json_decode($player_list_json, true);
            if (!$this->player_list) {
                error_log("Failed to decode player list JSON: " . json_last_error_msg());
            }
        } else {
            error_log("No player list found in Redis");
        }
    }
    
    private function loadAllPlayerStats() {
        // Only load if not already loaded
        if ($this->player_stats === null) {
            $stats_json = $this->redis->get('pickem_all_player_stats');
            if ($stats_json) {
                $this->player_stats = json_decode($stats_json, true);
                if (!$this->player_stats) {
                    error_log("Failed to decode player stats JSON: " . json_last_error_msg());
                    $this->player_stats = ['batters' => [], 'pitchers' => []];
                }
            } else {
                error_log("No player stats found in Redis");
                $this->player_stats = ['batters' => [], 'pitchers' => []];
            }
        }
        return $this->player_stats !== null;
    }
    
    private function loadPlayerBitmap($player_name) {
        // Only load if not already loaded
        if (!isset($this->loaded_player_bitmaps[$player_name])) {
            $bitmap_json = $this->redis->get("pickem_player_bitmap_{$player_name}");
            if ($bitmap_json) {
                $bitmap_data = json_decode($bitmap_json, true);
                if ($bitmap_data) {
                    $this->loaded_player_bitmaps[$player_name] = $bitmap_data;
                    return true;
                } else {
                    error_log("Failed to decode player bitmap JSON for {$player_name}: " . json_last_error_msg());
                    return false;
                }
            } else {
                error_log("No bitmap data found in Redis for player {$player_name}");
                return false;
            }
        }
        return true;
    }
    
    // Kept for backward compatibility
    public function loadFullData() {
        return $this->loadAllPlayerStats();
    }
    
    public function hasPlayer($player_name) {
        // Normalize player name
        $player_name = str_replace(' ', '_', strtolower($player_name));
        
        // Check if player is in the list
        if ($this->player_list) {
            return in_array($player_name, $this->player_list);
        }
        
        // Fall back to checking player stats
        if ($this->loadAllPlayerStats()) {
            return isset($this->player_stats['batters'][$player_name]) || 
                   isset($this->player_stats['pitchers'][$player_name]);
        }
        
        return false;
    }
    
    public function getProbability($prop_name) {
        // Parse the prop name to extract components
        $parts = explode('_', $prop_name);
        $player_name = $parts[0];
        
        // Try to find the full player name if it has underscores in it
        for ($i = 1; $i < count($parts); $i++) {
            // Check if this part is a stat type
            $stat_indicators = ['hits', 'home', 'runs', 'rbis', 'singles', 'doubles', 'stolen', 
                               'strikeouts', 'first', 'period', 'total', 'batter', 'fantasy', 
                               'walks', 'outs', 'pitch'];
            
            if (in_array($parts[$i], $stat_indicators)) {
                break;
            }
            
            $player_name .= '_' . $parts[$i];
        }
        
        // Extract stat type and threshold
        $remaining_parts = array_slice($parts, strlen($player_name) - strlen(str_replace('_', '', $player_name)) + 1);
        
        // Handle special cases for prop types
        if (count($remaining_parts) < 2) {
            error_log("Invalid prop format: {$prop_name}");
            return null;
        }
        
        $is_first_prop = false;
        $threshold = '';
        $stat_type = '';
        
        // Handle various prop types
        if ($remaining_parts[0] === 'first') {
            $is_first_prop = true;
            $stat_type = 'first_' . $remaining_parts[1];
            $threshold = '1';
        } else if (strpos(implode('_', $remaining_parts), 'period_1_2_3') !== false) {
            // Period 1-3 props
            $stat_parts = [];
            $found_plus = false;
            
            foreach ($remaining_parts as $part) {
                if ($part === 'plus') {
                    $found_plus = true;
                    continue;
                }
                
                if ($found_plus) {
                    continue;
                }
                
                if (is_numeric($part) && !$found_plus) {
                    $threshold = $part;
                } else {
                    $stat_parts[] = $part;
                }
            }
            
            $stat_type = implode('_', $stat_parts);
        } else {
            // Regular props
            // Last part is usually "plus"
            // Second to last part is the threshold
            // Everything before that is the stat type
            
            if ($remaining_parts[count($remaining_parts) - 1] === 'plus') {
                $threshold = $remaining_parts[count($remaining_parts) - 2];
                $stat_parts = array_slice($remaining_parts, 0, count($remaining_parts) - 2);
                $stat_type = implode('_', $stat_parts);
            }
        }
        
        if (empty($stat_type) || empty($threshold)) {
            error_log("Could not parse stat type or threshold from prop: {$prop_name}");
            return null;
        }
        
        // Get probability from preprocessed stats
        if ($this->loadAllPlayerStats()) {
            // Determine player type
            $player_type = null;
            if (isset($this->player_stats['batters'][$player_name])) {
                $player_type = 'batters';
            } else if (isset($this->player_stats['pitchers'][$player_name])) {
                $player_type = 'pitchers';
            }
            
            if ($player_type && isset($this->player_stats[$player_type][$player_name]['stats'][$stat_type][$threshold])) {
                $count = $this->player_stats[$player_type][$player_name]['stats'][$stat_type][$threshold];
                $total_sims = $this->player_stats[$player_type][$player_name]['total_sims'];
                return $count / $total_sims;
            }
        }
        
        // Fall back to bitmap data if needed
        if ($this->loadPlayerBitmap($player_name)) {
            $prop_key = $stat_type . '_' . $threshold . '_plus';
            if ($is_first_prop) {
                $prop_key = $stat_type;
            }
            
            if (isset($this->loaded_player_bitmaps[$player_name][$prop_key])) {
                $bitmap = $this->loaded_player_bitmaps[$player_name][$prop_key];
                
                if (!$this->metadata || !isset($this->metadata['num_sims']) || $this->metadata['num_sims'] == 0) {
                    error_log("Invalid metadata for calculating probabilities");
                    return null;
                }
                
                // Calculate probability
                $true_count = 0;
                foreach ($bitmap as $value) {
                    if ($value === true || $value === 1) {
                        $true_count++;
                    }
                }
                
                return $true_count / $this->metadata['num_sims'];
            }
        }
        
        error_log("No data found for prop: {$prop_name}");
        return null;
    }
    
    public function getPlayersLookupData() {
        // This is the main method we use - loads all player stats from Redis once
        if (!$this->loadAllPlayerStats()) {
            error_log("No player stats available for lookup data");
            return ['pitchers' => [], 'batters' => []];
        }
        
        $result = ['pitchers' => [], 'batters' => []];
        
        // Process the player stats directly
        foreach (['batters', 'pitchers'] as $player_type) {
            foreach ($this->player_stats[$player_type] as $player_name => $player_data) {
                // Calculate probabilities for each stat
                $player_result = [];
                foreach ($player_data['stats'] as $stat_type => $thresholds) {
                    $player_result[$stat_type] = [];
                    
                    foreach ($thresholds as $threshold => $count) {
                        $probability = $count / $player_data['total_sims'];
                        $player_result[$stat_type][$threshold] = $probability;
                    }
                }
                
                // Add to result
                $result[$player_type][$player_name] = $player_result;
            }
        }
        
        return $result;
    }
} 