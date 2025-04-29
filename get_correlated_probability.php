<?php
require_once 'config.php';
require_once 'redis_helper.php';
require_once 'bitmap_helper.php';

header('Content-Type: application/json');

try {
    // Get the POST data
    $data = json_decode(file_get_contents('php://input'), true);
    
    if (!$data || !isset($data['props']) || !is_array($data['props']) || count($data['props']) < 2) {
        throw new Exception('Invalid input data - must provide at least 2 props');
    }
    
    // Get Redis instance
    $redis = RedisHelper::getInstance();
    
    // Get all bitmaps
    $bitmaps = [];
    foreach ($data['props'] as $prop) {
        $player_key = strtolower(str_replace([' ', '-'], ['_', '#'], $prop['player']));
        $bitmap = $redis->get("pickem_player_bitmap_" . $player_key);
        
        if (!$bitmap) {
            throw new Exception("Player bitmap not found for: " . $prop['player']);
        }
        
        // Decode the JSON data
        $bitmap = json_decode($bitmap, true);
        if (!$bitmap) {
            throw new Exception('Failed to decode bitmap JSON data');
        }
        
        // Get the specific stat bitmap
        $stat_key = $prop['stat_name'];
        if (strpos($prop['stat_name'], 'first') === false) {
            $stat_key .= '_' . ceil($prop['stat_value']) . '_plus';
        }
        
        if (!isset($bitmap[$stat_key])) {
            throw new Exception("Stat bitmap not found for: " . $stat_key);
        }
        
        // The bitmap data is already a string, no need for base64_decode
        $bitmap_data = $bitmap[$stat_key];
        
        // Convert array of bytes back to string if needed
        if (is_array($bitmap_data)) {
            $bitmap_data = implode('', array_map('chr', $bitmap_data));
        }
        
        // Decompress the bitmap
        $decompressed = gzdecode($bitmap_data);
        if ($decompressed === false) {
            throw new Exception('Failed to decompress bitmap data');
        }
        
        // For under props, invert the bitmap
        if ($prop['type'] === 'under__') {
            $inverted = '';
            for ($i = 0; $i < strlen($decompressed); $i++) {
                $byte = ord($decompressed[$i]);
                $inverted .= chr(~$byte & 0xFF);
            }
            $decompressed = $inverted;
        }
        
        $bitmaps[] = $decompressed;
    }
    
    // Get the total number of simulations from metadata
    $metadata = $redis->get('pickem_simulation_metadata');
    if (!$metadata) {
        throw new Exception('Simulation metadata not found');
    }
    
    $metadata = json_decode($metadata, true);
    if (!isset($metadata['num_sims']) || $metadata['num_sims'] <= 0) {
        throw new Exception('Invalid num_sims in metadata');
    }
    
    $totalSims = $metadata['num_sims'];
    
    // Count the number of simulations where all props hit
    $allHit = 0;
    $allButOneHit = 0;
    $allButTwoHit = 0;
    
    for ($i = 0; $i < $totalSims; $i++) {
        $byteIndex = floor($i / 8);
        $bitIndex = $i % 8;
        
        // Count how many props hit in this simulation
        $propsHit = 0;
        foreach ($bitmaps as $bitmap) {
            $byte = ord(substr($bitmap, $byteIndex, 1));
            if ($byte & (1 << $bitIndex)) {
                $propsHit++;
            }
        }
        
        // Update counters based on number of props that hit
        if ($propsHit === count($bitmaps)) {
            $allHit++;
        } elseif ($propsHit === count($bitmaps) - 1) {
            $allButOneHit++;
        } elseif (count($bitmaps) >= 6 && $propsHit === count($bitmaps) - 2) {
            $allButTwoHit++;
        }
    }
    
    // Calculate the probabilities
    $jointProbability = $allHit / $totalSims;
    $allButOneProbability = $allButOneHit / $totalSims;
    $allButTwoProbability = count($bitmaps) >= 6 ? $allButTwoHit / $totalSims : null;
    
    $response = [
        'success' => true,
        'correlated_probability' => $jointProbability,
        'all_but_one_probability' => $allButOneProbability
    ];
    
    if ($allButTwoProbability !== null) {
        $response['all_but_two_probability'] = $allButTwoProbability;
    }
    
    echo json_encode($response);
    
} catch (Exception $e) {
    error_log("Error in get_correlated_probability.php: " . $e->getMessage());
    echo json_encode([
        'success' => false,
        'error' => $e->getMessage()
    ]);
} 