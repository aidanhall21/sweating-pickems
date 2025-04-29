<?php
require_once 'config.php';
require_once 'redis_helper.php';
require_once 'bitmap_helper.php';
// Increase memory limit for large simulation data
ini_set('memory_limit', '512M');
session_start();

// Function to fetch props from Underdog using the Python scraper
function fetchUnderdogProps() {
    if (!file_exists('data')) mkdir('data', 0755, true);
    
    // Create a session directory if needed
    $session_id = session_id();
    $session_dir = "data/sessions/$session_id";
    if (!file_exists($session_dir)) {
        mkdir($session_dir, 0755, true);
    }
    
    error_log("Fetching Underdog props for session: $session_id");
    exec("python3 scripts/fetch_props.py --session-id $session_id 2>&1", $output, $return_var);
    
    if ($return_var !== 0) {
        error_log("Error fetching props: " . implode("\n", $output));
        throw new Exception("Failed to fetch props");
    }
    
    $props_file = "$session_dir/underdog_props.json";
    error_log("Expected props file location: $props_file");
    
    if (!file_exists($props_file)) {
        error_log("Underdog props data file not found at expected location");
        throw new Exception("Underdog props data file not found");
    }
    
    error_log("Successfully loaded props from: $props_file");
    // Just return the props directly - we'll handle simulation data separately
    return json_decode(file_get_contents($props_file), true);
}

// Function to find similar player names
function findSimilarPlayerName($name, $playersList, $threshold = 3) {
    // Normalize name for comparison (remove accents, suffixes)
    $normalizedName = normalizePlayerName($name);
    
    // First try exact match with normalized names
    foreach (array_keys($playersList) as $playerName) {
        $normalizedPlayerName = normalizePlayerName($playerName);
        if ($normalizedName === $normalizedPlayerName) {
            return $playerName;
        }
    }
    
    $bestMatch = null;
    $bestDistance = PHP_INT_MAX;
    
    // First word of player name (usually first name)
    $nameParts = explode('_', $name);
    $firstName = isset($nameParts[0]) ? $nameParts[0] : '';
    $lastName = isset($nameParts[1]) ? $nameParts[1] : '';
    
    foreach (array_keys($playersList) as $playerName) {
        $normalizedPlayerName = normalizePlayerName($playerName);
        $playerParts = explode('_', $playerName);
        $playerFirstName = isset($playerParts[0]) ? $playerParts[0] : '';
        $playerLastName = isset($playerParts[1]) ? $playerParts[1] : '';
        
        // Skip if first letter of first name doesn't match
        if ($firstName && $playerFirstName && $firstName[0] !== $playerFirstName[0]) {
            continue;
        }
        
        // Skip if last names are too different (more than 2 characters different)
        if ($lastName && $playerLastName) {
            $lastNameDistance = levenshtein($lastName, $playerLastName);
            if ($lastNameDistance > 2) {
                continue;
            }
        }
        
        $distance = levenshtein($normalizedName, $normalizedPlayerName);
        if ($distance < $bestDistance && $distance <= $threshold) {
            // Make sure we're not matching significantly different names
            // Calculate match quality (1.0 = perfect match, 0.0 = completely different)
            $matchQuality = 1.0 - ($distance / max(strlen($normalizedName), strlen($normalizedPlayerName)));
            
            // Require at least 70% similarity for a match
            if ($matchQuality >= 0.7) {
                $bestDistance = $distance;
                $bestMatch = $playerName;
            }
        }
    }
    
    return $bestMatch;
}

// Helper function to normalize player names for comparison
function normalizePlayerName($name) {
    // Remove accents
    $normalized = iconv('UTF-8', 'ASCII//TRANSLIT', $name);
    
    // Convert to lowercase
    $normalized = strtolower($normalized);
    
    // Remove Jr., Sr., III, etc.
    $normalized = preg_replace('/_jr\.?$|_sr\.?$|_iii$|_ii$|_iv$/', '', $normalized);
    
    return $normalized;
}

// API endpoint to fetch props
if (isset($_GET['action']) && $_GET['action'] == 'fetch_props') {
    try {
        // Get the Redis helper correctly using the static getInstance method
        $redis = RedisHelper::getInstance();
        $debug_messages = []; // Initialize debug_messages array
        
        // Create the response object
        $response = [
            'success' => true,
            'data' => [
                'props' => fetchUnderdogProps(),
                'lookup' => ['batters' => [], 'pitchers' => []],
                'simulation_metadata' => $redis->get('pickem_simulation_metadata') ?: null
            ]
        ];
        
        // Directly load the player stats from Redis
        $player_stats_json = $redis->get('pickem_all_player_stats');
        if (!$player_stats_json) {
            $debug_messages[] = "No simulation data found in Redis (pickem_all_player_stats)";
        } else {
            $player_stats = json_decode($player_stats_json, true);
            if (!$player_stats) {
                $debug_messages[] = "Failed to decode player stats JSON: " . json_last_error_msg();
            } else {
                // Process the player stats to create lookup data
                foreach (['batters', 'pitchers'] as $player_type) {
                    foreach ($player_stats[$player_type] as $player_name => $player_data) {
                        $player_result = [];
                        foreach ($player_data['stats'] as $stat_type => $thresholds) {
                            $player_result[$stat_type] = [];
                            
                            foreach ($thresholds as $threshold => $count) {
                                $probability = $count / $player_data['total_sims'];
                                $player_result[$stat_type][$threshold] = $probability;
                            }
                        }
                        
                        // Add to result
                        $response['data']['lookup'][$player_type][$player_name] = $player_result;
                    }
                }
                
                // Process props with the lookup data
                foreach ($response['data']['props'] as &$prop) {
                    
                    $player_name = strtolower($prop['selection_header']);
                    // Replace spaces with underscores to match props format
                    $player_name = strtolower(str_replace([' ', '-'], ['_', '#'], $player_name));
                    $stat_name = strtolower($prop['stat_name']);
                    $stat_value = floatval($prop['stat_value']);
                    
                    // Check if player exists using lookup data
                    $player_exists = false;
                    if (isset($response['data']['lookup']['batters'][$player_name])) {
                        $player_exists = true;
                        $player_type = 'batters';
                    } else if (isset($response['data']['lookup']['pitchers'][$player_name])) {
                        $player_exists = true;
                        $player_type = 'pitchers';
                    }
                    
                    // If player not found, try to find a similar name
                    if (!$player_exists) {
                        // Try batters first
                        $similar_name = findSimilarPlayerName($player_name, $response['data']['lookup']['batters']);
                        if ($similar_name) {
                            $player_exists = true;
                            $player_type = 'batters';
                            // $debug_messages[] = "Using similar batter name for '$player_name': '$similar_name'";
                            $player_name = $similar_name;
                            // Format the similar name to look like a proper player name
                            $formatted_name = ucwords(str_replace('_', ' ', $similar_name));
                            $prop['selection_header'] = $formatted_name;
                        } else {
                            // Try pitchers if no batter found
                            $similar_name = findSimilarPlayerName($player_name, $response['data']['lookup']['pitchers']);
                            if ($similar_name) {
                                $player_exists = true;
                                $player_type = 'pitchers';
                                // $debug_messages[] = "Using similar pitcher name for '$player_name': '$similar_name'";
                                $player_name = $similar_name;
                                // Format the similar name to look like a proper player name
                                $formatted_name = ucwords(str_replace('_', ' ', $similar_name));
                                $prop['selection_header'] = $formatted_name;
                            }
                        }
                    }
                    
                    if (!$player_exists) {
                        // $debug_messages[] = "Player not found in simulation data: $player_name";
                        continue;
                    }
                    
                    // Check if stat exists in player's simulation data
                    if (!isset($response['data']['lookup'][$player_type][$player_name][$stat_name])) {
                        // $debug_messages[] = "Stat '$stat_name' not found in simulation data for player: $player_name";
                        continue;
                    }

                    $threshold = ceil($stat_value);
                    
                    // Get the probability directly from the lookup data
                    if (isset($response['data']['lookup'][$player_type][$player_name][$stat_name][$threshold])) {
                        $probability = $response['data']['lookup'][$player_type][$player_name][$stat_name][$threshold];
                        
                        // Adjust for lower props
                        if ($prop['choice_id'] === 'under__') {
                            $probability = 1 - $probability;
                        }
                        
                        $prop['simulation_probability'] = $probability;
                    } else {
                        $debug_messages[] = "No probability found for player: $player_name, stat: $stat_name, threshold: $threshold";
                    }
                }
            }
        }
        
        header('Content-Type: application/json');
        echo json_encode($response);
        
        // Log debug messages after sending response
        foreach ($debug_messages as $message) {
            error_log($message);
        }
    } catch (Exception $e) {
        header('Content-Type: application/json');
        echo json_encode(['success' => false, 'error' => $e->getMessage()]);
    }
    exit;
}

?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>View Props - MLB Pick'em Simulator</title>
    <link rel="apple-touch-icon" sizes="180x180" href="favicon/apple-touch-icon.png">
    <link rel="icon" type="image/png" sizes="32x32" href="favicon/favicon-32x32.png">
    <link rel="icon" type="image/png" sizes="16x16" href="favicon/favicon-16x16.png">
    <link rel="manifest" href="favicon/site.webmanifest">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="css/style.css" rel="stylesheet">
    <style>
        .prop-item {
            display: flex;
            align-items: flex-start;
            padding: 0.75rem;
            border-bottom: 1px solid #eee;
            gap: 1rem;
            flex-wrap: wrap;
            flex-direction: column;
        }
        .prop-stat {
            flex: 1;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            min-width: 180px;
            width: 100%;
            margin-bottom: 8px;
            font-size: 1.1em;
        }
        .prop-value {
            font-weight: bold;
            white-space: nowrap;
        }
        .prop-buttons {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            width: 100%;
            align-items: center;
        }
        .prop-button {
            padding: 0.5rem 1rem;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 500;
            transition: all 0.2s;
            background-color: #f5f5f5;
            color: #424242;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            min-width: 120px;
        }
        .prop-button:hover {
            background-color: #e0e0e0;
        }
        .prop-button.selected {
            background-color: #007bff;
            color: white;
            outline: none;
        }
        .probability {
            font-size: 0.8em;
            padding: 0.2rem 0.4rem;
            border-radius: 3px;
            color: #424242;
        }
        .probability-red {
            background-color: #ffcdd2;
        }
        .probability-yellow {
            background-color: #ffe0b2;
        }
        .probability-green {
            background-color: #c8e6c9;
        }
        #selected-props {
            max-height: 300px;
            overflow-y: auto;
        }
        .selected-prop-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.5rem;
            background-color: #f5f5f5;
            margin-bottom: 0.5rem;
            border-radius: 4px;
        }
        .remove-prop {
            color: #424242;
            cursor: pointer;
            padding: 0.25rem 0.5rem;
        }
        .simulation-prob {
            margin-left: 4px;
            font-style: italic;
            border-left: 1px solid #ddd;
            padding-left: 4px;
            font-weight: bold;
            font-size: 0.9em;
        }
        .props-layout {
            position: relative;
        }
        .props-content {
            margin-right: 370px;
        }
        .props-sidebar {
            position: fixed;
            right: 20px;
            top: 100px;
            width: 350px;
            background: white;
            z-index: 100;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        .props-sidebar .card {
            margin-bottom: 0;
        }
        .props-sidebar .card-body {
            padding-bottom: 15px;
        }
        .analyze-btn-container {
            margin-bottom: 0;
        }
        .combined-probability {
            margin-top: 15px;
            padding: 10px;
            background-color: #f8f9fa;
            border-radius: 4px;
            font-size: 0.9em;
            text-align: center;
        }
        .combined-probability-value {
            font-weight: bold;
            font-size: 1.1em;
        }
        .combined-probability-odds {
            display: block;
            margin-top: 5px;
            font-style: italic;
            color: #666;
        }
        .payout-multipliers {
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #eee;
        }
        .payout-item {
            margin-bottom: 10px;
        }
        .payout-item:last-child {
            margin-bottom: 0;
        }
        .payout-item ul {
            margin-top: 5px;
            padding-left: 20px;
        }
        .payout-item li {
            margin-bottom: 3px;
        }
        .payout-item li:last-child {
            margin-bottom: 0;
        }
        .error-message {
            margin-bottom: 15px;
            padding: 10px;
            border-radius: 4px;
            font-size: 0.9em;
        }
        .error-message br {
            margin-bottom: 5px;
            display: block;
            content: "";
        }
        @media (max-width: 992px) {
            .props-content {
                margin-right: 0;
            }
            .props-sidebar {
                position: static;
                width: 100%;
                margin-top: 20px;
                margin-bottom: 20px;
                box-shadow: none;
            }
        }
        .alt-prop-container {
            margin-top: 10px;
            padding: 10px;
            background-color: #f9f9f9;
            border-radius: 4px;
            border: 1px solid #ddd;
            display: none; /* Initially hidden */
            width: 100%;
        }
        .alt-prop-row {
            display: flex;
            gap: 8px;
            margin-bottom: 8px;
            align-items: center;
        }
        .alt-prop-value {
            font-weight: bold;
            min-width: 50px;
        }
        .alt-button {
            margin-left: auto;
        }
        .alt-prop-buttons {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }
        .alt-prop-button {
            padding: 0.5rem 1rem;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 500;
            transition: all 0.2s;
            background-color: #f5f5f5;
            color: #424242;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            min-width: 120px;
        }
        .alt-prop-button:hover {
            background-color: #e0e0e0;
        }
        .alt-prop-button.selected {
            background-color: #007bff;
            color: white;
            outline: none;
        }
        /* Remove the style that changes simulation probability color for selected buttons */
        .prop-button.selected .simulation-prob, 
        .alt-prop-button.selected .simulation-prob {
            background-color: inherit !important;
            color: inherit !important;
            border: none;
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="index.php">MLB Pick'em Simulator</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav">
                    <li class="nav-item">
                        <a class="nav-link" href="upload.php">Upload Projections</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link active" href="props.php">View Props</a>
                    </li>
                </ul>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        <h1>Available Props</h1>
        <p>Browse and select props from Underdog. Selected props will be analyzed for positive EV opportunities.</p>
        
        <div class="d-flex justify-content-between align-items-center mb-4">
            <div>
                <button id="fetch-props" class="btn btn-primary">
                    <span id="loading-spinner" class="spinner-border spinner-border-sm" role="status" aria-hidden="true" style="display: none;">
                        <span class="visually-hidden">Loading...</span>
                    </span>
                    Fetch Props
                </button>
            </div>
        </div>
        
        <div id="fetch-message" class="text-center text-muted mb-4">
            Click the button above to fetch the latest available props.
        </div>
        
        <div id="props-container" class="props-layout" style="display: none;">
            <div class="props-content">
                <div id="props-list">
                    <!-- Props will be loaded here via JavaScript -->
                </div>
            </div>
            
            <div class="props-sidebar">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">Selected Props</h5>
                    </div>
                    <div class="card-body">
                        <div id="selected-props"></div>
                        <div id="combined-probability" class="combined-probability" style="display: none;">
                            Combined probability: <span class="combined-probability-value">0%</span>
                            <span class="combined-probability-odds"></span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            // Change from a Set to an Object to store full prop data
            const selectedProps = {};
            const analyzeButton = document.getElementById('analyze-props');
            const selectedPropsContainer = document.getElementById('selected-props');
            const fetchButton = document.getElementById('fetch-props');
            const loadingSpinner = document.getElementById('loading-spinner');
            const propsContainer = document.getElementById('props-container');
            const fetchMessage = document.getElementById('fetch-message');
            const propsList = document.getElementById('props-list');
            const combinedProbabilityDiv = document.getElementById('combined-probability');
            const combinedProbabilityValue = document.querySelector('.combined-probability-value');
            const combinedProbabilityOdds = document.querySelector('.combined-probability-odds');
            
            // Hide loading spinner initially
            loadingSpinner.style.display = 'none';
            
            // Function to update combined probability
            async function updateCombinedProbability() {
                const propsArray = Object.values(selectedProps);
                
                if (propsArray.length <= 1) {
                    combinedProbabilityDiv.style.display = 'none';
                    return;
                }
                
                try {
                    // Prepare the data for the correlated probability calculation
                    const requestData = {
                        props: propsArray.map(prop => ({
                            player: prop.player,
                            stat_name: prop.stat_name,
                            stat_value: prop.stat_value,
                            type: prop.type
                        }))
                    };
                    
                    // Call the endpoint to calculate joint probability
                    const response = await fetch('get_correlated_probability.php', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(requestData)
                    });
                    
                    if (!response.ok) {
                        throw new Error('Failed to calculate joint probability');
                    }
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        // Clear existing content
                        combinedProbabilityDiv.innerHTML = '';
                        
                        // Add probability value
                        const probabilityPercentage = (data.correlated_probability * 100).toFixed(2);
                        combinedProbabilityDiv.innerHTML = `
                            Combined probability: <span class="combined-probability-value">${probabilityPercentage}%</span>
                            <span class="combined-probability-odds"></span>
                        `;
                        
                        // Update reference to the new elements
                        const combinedProbabilityValue = combinedProbabilityDiv.querySelector('.combined-probability-value');
                        
                        // Color code based on probability
                        if (data.correlated_probability < 0.25) {
                            combinedProbabilityValue.style.color = '#d32f2f'; // Red
                        } else if (data.correlated_probability < 0.5) {
                            combinedProbabilityValue.style.color = '#f57c00'; // Orange
                        } else {
                            combinedProbabilityValue.style.color = '#388e3c'; // Green
                        }

                        // Make the Underdog API call to get payout multipliers
                        const options = propsArray.map(prop => ({
                            id: prop.options_id,
                            type: 'OverUnderOption'
                        }));

                        const params = new URLSearchParams();
                        options.forEach(option => {
                            params.append('options[][id]', option.id);
                            params.append('options[][type]', option.type);
                        });

                        const underdogResponse = await fetch(`https://api.underdogfantasy.com/v4/entry_slips/payout_outcome?${params.toString()}`);
                        if (!underdogResponse.ok) {
                            throw new Error('Failed to fetch payout multipliers');
                        }

                        const underdogData = await underdogResponse.json();

                        // If there are any errors, don't show combined probability or payouts
                        if (underdogData.errors && underdogData.errors.length > 0) {
                            combinedProbabilityDiv.style.display = 'block';
                            combinedProbabilityDiv.innerHTML = `
                                <div class="error-message">
                                    ${underdogData.errors.map(error => `
                                        <strong>${error.title}</strong><br>
                                        ${error.detail}
                                    `).join('<br><br>')}
                                </div>
                            `;
                            return;
                        }

                        // Create payout multipliers div
                        let payoutHtml = '<div class="payout-multipliers mt-3">';
                        
                        // Calculate EVs
                        let standardEV = 0;
                        let insuranceEV = 0;
                        
                        // Standard payout
                        if (underdogData.standard && underdogData.standard.payout_multiplier) {
                            standardEV = (data.correlated_probability * (underdogData.standard.payout_multiplier - 1)) + (-1 * (1 - data.correlated_probability));
                            payoutHtml += `
                                <div class="payout-item">
                                    <strong>Standard Payout:</strong> ${underdogData.standard.payout_multiplier}x 
                                    <span class="text-muted">(EV: ${(standardEV * 100).toFixed(1)}%)</span>
                                </div>
                            `;
                        }

                        // Insurance payout - only show if no errors
                        if (underdogData.insurance && underdogData.insurance.payout_multiplier && (!underdogData.insurance.errors || underdogData.insurance.errors.length === 0)) {
                            insuranceEV = data.correlated_probability * (underdogData.insurance.payout_multiplier - 1);
                            
                            // Add all_but_one probability with first fallback
                            if (data.all_but_one_probability && underdogData.insurance.fallbacks && underdogData.insurance.fallbacks.length > 0) {
                                insuranceEV += data.all_but_one_probability * (underdogData.insurance.fallbacks[0].payout_multiplier - 1);
                            }
                            
                            // Add all_but_two probability with second fallback if available
                            if (data.all_but_two_probability && underdogData.insurance.fallbacks && underdogData.insurance.fallbacks.length > 1) {
                                insuranceEV += data.all_but_two_probability * (underdogData.insurance.fallbacks[1].payout_multiplier - 1);
                            }
                            
                            // Subtract probability of missing more than allowed
                            const remainingProb = 1 - data.correlated_probability - (data.all_but_one_probability || 0) - (data.all_but_two_probability || 0);
                            insuranceEV -= remainingProb;
                            
                            payoutHtml += `
                                <div class="payout-item">
                                    <strong>Insurance Payout:</strong> ${underdogData.insurance.payout_multiplier}x 
                                    <span class="text-muted">(EV: ${(insuranceEV * 100).toFixed(1)}%)</span>
                                </div>
                            `;
                        }

                        // Fallback payouts
                        if (underdogData.insurance && underdogData.insurance.fallbacks && underdogData.insurance.fallbacks.length > 0) {
                            payoutHtml += '<div class="payout-item"><strong>Fallback Payouts:</strong><ul class="mb-0">';
                            underdogData.insurance.fallbacks.forEach(fallback => {
                                payoutHtml += `
                                    <li>${fallback.loss_count} loss: ${fallback.payout_multiplier}x</li>
                                `;
                            });
                            payoutHtml += '</ul></div>';
                        }

                        payoutHtml += '</div>';
                        
                        // Update combined probability color based on EVs
                        if (underdogData.insurance && underdogData.insurance.payout_multiplier && (!underdogData.insurance.errors || underdogData.insurance.errors.length === 0)) {
                            // Both standard and insurance exist
                            if (standardEV > 0 && insuranceEV > 0) {
                                combinedProbabilityValue.style.color = '#388e3c'; // Green
                            } else if (standardEV > 0 || insuranceEV > 0) {
                                combinedProbabilityValue.style.color = '#f57c00'; // Yellow/Orange
                            } else {
                                combinedProbabilityValue.style.color = '#d32f2f'; // Red
                            }
                        } else {
                            // Only standard exists
                            if (standardEV > 0) {
                                combinedProbabilityValue.style.color = '#388e3c'; // Green
                            } else {
                                combinedProbabilityValue.style.color = '#d32f2f'; // Red
                            }
                        }
                        
                        // Append the payout information to the combined probability div
                        combinedProbabilityDiv.innerHTML += payoutHtml;
                        combinedProbabilityDiv.style.display = 'block';
                    } else {
                        throw new Error(data.error || 'Failed to calculate joint probability');
                    }
                } catch (error) {
                    console.error('Error:', error);
                    combinedProbabilityDiv.style.display = 'none';
                }
            }
            
            // Function to load props into the UI
            function loadProps(props) {
                // Clear existing props
                propsList.innerHTML = '';
                
                // Group props by game, team, and player
                const groupedProps = {};
                props.forEach(prop => {
                    // Skip props without full_team_names_title
                    if (!prop.full_team_names_title) {
                        return;
                    }
                    
                    // Skip games in the past or next day (Eastern Time)
                    if (prop.scheduled_at) {
                        const gameTime = new Date(prop.scheduled_at);
                        // Get current time in Eastern timezone
                        const now = new Date().toLocaleString("en-US", {timeZone: "America/New_York"});
                        const nowET = new Date(now);
                        
                        // Convert UTC to Eastern Time (UTC-4 or UTC-5 depending on DST)
                        const easternTime = new Date(gameTime);
                        // Get timezone offset in minutes and convert to hours
                        const tzOffset = easternTime.getTimezoneOffset() / 60;
                        
                        // Determine if DST is in effect
                        const isDST = function() {
                            const jan = new Date(nowET.getFullYear(), 0, 1);
                            const jul = new Date(nowET.getFullYear(), 6, 1);
                            return Math.max(jan.getTimezoneOffset(), jul.getTimezoneOffset()) > nowET.getTimezoneOffset();
                        };
                        
                        const isDSTActive = isDST();
                        const etOffset = isDSTActive ? 4 : 5;
                        const hourDiff = etOffset - tzOffset;
                                                
                        // Apply the difference to convert to Eastern Time
                        easternTime.setHours(easternTime.getHours() - hourDiff);
                        
                        // Create tomorrow date (midnight Eastern Time)
                        const tomorrow = new Date(nowET);
                        tomorrow.setDate(tomorrow.getDate() + 1);
                        tomorrow.setHours(0, 0, 0, 0);

                        // Check if game is in the past
                        if (easternTime < nowET) {
                            return;
                        }
                        
                        // Check if game is scheduled for the next day
                        if (easternTime >= tomorrow) {
                            return;
                        }
                    }
                    
                    const game = prop.full_team_names_title;
                    const [awayTeamName, homeTeamName] = prop.full_team_names_title.split(' @ ');
                    const team = prop.team_id;
                    const teamName = prop.team_id === prop.away_team_id ? awayTeamName : homeTeamName;
                    const player = prop.selection_header;
                    
                    if (!groupedProps[game]) {
                        groupedProps[game] = {
                            title: game,
                            teams: {}
                        };
                    }
                    if (!groupedProps[game].teams[team]) {
                        groupedProps[game].teams[team] = {
                            name: teamName,
                            players: {}
                        };
                    }
                    if (!groupedProps[game].teams[team].players[player]) {
                        groupedProps[game].teams[team].players[player] = [];
                    }
                    
                    groupedProps[game].teams[team].players[player].push(prop);
                });
                
                // Render props
                Object.entries(groupedProps).forEach(([game, gameData]) => {
                    const gameDiv = document.createElement('div');
                    gameDiv.className = 'card mb-3';
                    gameDiv.innerHTML = `
                        <div class="card-header" data-bs-toggle="collapse" data-bs-target="#game-${btoa(game)}" style="cursor: pointer;">
                            <h5 class="mb-0">${gameData.title}</h5>
                        </div>
                        <div class="collapse" id="game-${btoa(game)}">
                            <div class="card-body">
                                ${Object.entries(gameData.teams).map(([team, teamData]) => `
                                    <div class="card mb-3">
                                        <div class="card-header" data-bs-toggle="collapse" data-bs-target="#team-${btoa(team)}" style="cursor: pointer;">
                                            <h6 class="mb-0">${teamData.name}</h6>
                                        </div>
                                        <div class="collapse" id="team-${btoa(team)}">
                                            <div class="card-body">
                                                ${Object.entries(teamData.players).map(([player, playerProps]) => `
                                                    <div class="card mb-2">
                                                        <div class="card-header" data-bs-toggle="collapse" data-bs-target="#player-${btoa(player)}" style="cursor: pointer;">
                                                            <h6 class="mb-0">${player}</h6>
                                                        </div>
                                                        <div class="collapse" id="player-${btoa(player)}">
                                                            <div class="card-body">
                                                                ${((currentPlayer, currentPlayerProps) => {
                                                                    // Group playerProps by stat_name + stat_value + over_under_id
                                                                    const groupedByStat = {};
                                                                    currentPlayerProps.forEach(prop => {
                                                                        const key = `${prop.stat_name}|${prop.stat_value}|${prop.over_under_id}`;
                                                                        if (!groupedByStat[key]) groupedByStat[key] = [];
                                                                        groupedByStat[key].push(prop);
                                                                    });
                                                                    return Object.values(groupedByStat).map(group => {
                                                                        // All props in group share stat_name, stat_value, over_under_id
                                                                        const mainProp = group[0];
                                                                        const playerName = currentPlayer.toLowerCase().replace(/\s+/g, '_').replace(/-/g, '#');
                                                                        const pitcherData = window.lookupData?.pitchers?.[playerName] || window.lookupData?.pitchers?.[currentPlayer] || window.lookupData?.pitchers?.[currentPlayer.toLowerCase()];
                                                                        const batterData = window.lookupData?.batters?.[playerName] || window.lookupData?.batters?.[currentPlayer] || window.lookupData?.batters?.[currentPlayer.toLowerCase()];
                                                                        const playerData = pitcherData || batterData;
                                                                        return `
                                                                            <div class="prop-item">
                                                                                <div class="prop-stat">
                                                                                    <span class="prop-value">
                                                                                        ${mainProp.display_stat}: ${mainProp.stat_value}
                                                                                    </span>
                                                                                </div>
                                                                                <div class="prop-buttons">
                                                                                    ${group.map(prop => `
                                                                                        ${prop.payout_multiplier ? `
                                                                                            <button class="prop-button" data-prop='${(() => {
                                                                                                return JSON.stringify({
                                                                                                    id: prop.id,
                                                                                                    over_under_id: prop.over_under_id,
                                                                                                    options_id: prop.options_id,
                                                                                                    appearance_id: prop.appearance_id,
                                                                                                    player: prop.selection_header,
                                                                                                    team: teamData.name,
                                                                                                    stat_name: prop.stat_name,
                                                                                                    display_stat: prop.display_stat,
                                                                                                    stat_value: prop.stat_value,
                                                                                                    type: prop.choice_id,
                                                                                                    choice_display: prop.choice_display,
                                                                                                    multiplier: prop.payout_multiplier,
                                                                                                    simulation_probability: prop.simulation_probability,
                                                                                                    match_id: prop.match_id,
                                                                                                    player_id: prop.player_id,
                                                                                                    team_id: prop.team_id,
                                                                                                    scheduled_at: prop.scheduled_at,
                                                                                                    has_alternates: prop.has_alternates
                                                                                                });
                                                                                            })()}' data-prop-id="${prop.id}-${prop.choice_id}">
                                                                                                ${prop.choice_display} (${prop.payout_multiplier}x)
                                                                                                ${prop.simulation_probability !== undefined ? `
                                                                                                    <span class="probability simulation-prob ${prop.simulation_probability * prop.payout_multiplier < 0.549 ? 'probability-red' : prop.simulation_probability * prop.payout_multiplier < 0.577 ? 'probability-yellow' : 'probability-green'}">
                                                                                                        Sim: ${(prop.simulation_probability * 100).toFixed(1)}%
                                                                                                    </span>
                                                                                                ` : ''}
                                                                                            </button>
                                                                                        ` : ''}
                                                                                    `).join('')}
                                                                                    ${group.some(prop => prop.has_alternates) ? `
                                                                                        <button class="alt-button btn btn-sm btn-outline-secondary" 
                                                                                            data-over-under-id="${group[0].over_under_id}" 
                                                                                            data-alt-target="alt-${group[0].over_under_id}"
                                                                                            data-prop='${JSON.stringify({
                                                                                                player: mainProp.selection_header,
                                                                                                team: teamData.name,
                                                                                                stat_name: mainProp.stat_name,
                                                                                                display_stat: mainProp.display_stat,
                                                                                                stat_value: mainProp.stat_value
                                                                                            })}'>
                                                                                            ALT
                                                                                        </button>
                                                                                    ` : ''}
                                                                                </div>
                                                                                ${group.some(prop => prop.has_alternates) ? `
                                                                                    <div class="alt-prop-container" id="alt-${group[0].over_under_id}"></div>
                                                                                ` : ''}
                                                                            </div>
                                                                        `;
                                                                    }).join('');
                                                                })(player, playerProps)}
                                                            </div>
                                                        </div>
                                                    </div>
                                                `).join('')}
                                            </div>
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    `;
                    propsList.appendChild(gameDiv);
                });
                
                // Add click handlers for prop buttons
                document.querySelectorAll('.prop-button').forEach(button => {
                    button.addEventListener('click', function() {
                        const propData = JSON.parse(this.dataset.prop);
                        const propId = propData.id + '-' + propData.type;
                        
                        // Check if player already has a prop selected
                        const existingProp = Object.values(selectedProps).find(p => p.player === propData.player && (p.id + '-' + p.type) !== propId);
                        if (existingProp) {
                            // Deselect the existing prop
                            const existingPropId = existingProp.id + '-' + existingProp.type;
                            console.log('Regular prop: Replacing existing prop:', existingPropId, existingProp.player);
                            
                            // Find and deselect the existing button (either regular or alt)
                            const existingButton = document.querySelector(`.prop-button[data-prop*='"id":"${existingProp.id}"'][data-prop*='"type":"${existingProp.type}"']`) ||
                                                 document.querySelector(`.alt-prop-button[data-prop*='"id":"${existingProp.id}"'][data-prop*='"type":"${existingProp.type}"']`);
                            if (existingButton) {
                                existingButton.classList.remove('selected');
                                console.log('Regular prop: Found and deselected button for', existingProp.player);
                            } else {
                                console.log('Regular prop: Could not find existing button to deselect for', existingProp.player);
                            }
                            
                            // Remove from selected props object and UI
                            delete selectedProps[existingPropId];
                            const existingElement = document.getElementById('prop-' + existingPropId);
                            if (existingElement) {
                                existingElement.remove();
                                console.log('Regular prop: Removed existing element from display');
                            }
                        }
                        
                        // Toggle selection state for this button
                        if (this.classList.contains('selected')) {
                            // Deselect this prop
                            this.classList.remove('selected');
                            delete selectedProps[propId];
                            document.getElementById('prop-' + propId)?.remove();
                        } else {
                            // Select this prop
                            if (Object.keys(selectedProps).length >= 8) {
                                alert('Maximum of 8 props allowed');
                                return;
                            }
                            
                            this.classList.add('selected');
                            selectedProps[propId] = propData;
                            
                            // Create selected prop display
                            const propElement = document.createElement('div');
                            propElement.id = 'prop-' + propId;
                            propElement.className = 'selected-prop-item';
                            propElement.innerHTML = `
                                <div>
                                    <strong>${propData.player}</strong> (${propData.team})<br>
                                    ${propData.display_stat}: ${propData.choice_display} ${propData.stat_value} (${propData.multiplier}x)
                                </div>
                                <span class="remove-prop" data-prop-id="${propId}">&times;</span>
                            `;
                            selectedPropsContainer.appendChild(propElement);
                            
                            // Scroll to the bottom of selected props to show the newly added item
                            selectedPropsContainer.scrollTop = selectedPropsContainer.scrollHeight;
                        }
                        
                        updateCombinedProbability();
                    });
                });
            }
            
            // Fetch props
            fetchButton.addEventListener('click', function() {
                loadingSpinner.style.display = 'inline-block';
                fetchButton.disabled = true;
                fetchMessage.style.display = 'none';
                
                fetch('props.php?action=fetch_props')
                    .then(response => {
                        if (!response.ok) {
                            throw new Error('Network response was not ok');
                        }
                        return response.json();
                    })
                    .then(data => {
                        if (data.success && data.data && data.data.props) {
                            
                            window.lookupData = data.data.lookup; // Store lookup data globally
                            loadProps(data.data.props);
                            propsContainer.style.display = 'block';
                        } else {
                            throw new Error('Invalid data structure received');
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        alert('An error occurred while fetching props. Please try again.');
                        fetchMessage.style.display = 'block';
                    })
                    .finally(() => {
                        loadingSpinner.style.display = 'none';
                        fetchButton.disabled = false;
                    });
            });

            // Update the remove prop handler
            selectedPropsContainer.addEventListener('click', function(e) {
                if (e.target.classList.contains('remove-prop')) {
                    const propId = e.target.dataset.propId;
                    
                    // Direct selector using the data-prop-id attribute
                    const button = document.querySelector(`[data-prop-id="${propId}"]`);
                    if (button) {
                        button.classList.remove('selected');
                    }
                    
                    delete selectedProps[propId];
                    document.getElementById('prop-' + propId).remove();
                    
                    updateCombinedProbability();
                }
            });
            
            // Update the alt prop button handler
            document.addEventListener('click', function(e) {
                // First handle alt props
                if (e.target.classList.contains('alt-prop-button')) {
                    const propData = JSON.parse(e.target.dataset.prop);
                    const propId = propData.id + '-' + propData.type;
                    
                    // Check if player already has a prop selected
                    const existingProp = Object.values(selectedProps).find(p => p.player === propData.player);
                    if (existingProp) {
                        // Deselect the existing prop
                        const existingPropId = existingProp.id + '-' + existingProp.type;
                        console.log('Replacing existing prop:', existingPropId, existingProp.player);
                        
                        // Find and deselect the existing button (either regular or alt)
                        const existingButton = document.querySelector(`.prop-button[data-prop*='"id":"${existingProp.id}"'][data-prop*='"type":"${existingProp.type}"']`) ||
                                             document.querySelector(`.alt-prop-button[data-prop*='"id":"${existingProp.id}"'][data-prop*='"type":"${existingProp.type}"']`);
                        if (existingButton) {
                            existingButton.classList.remove('selected');
                            console.log('Found and deselected button for', existingProp.player);
                        } else {
                            console.log('Could not find existing button to deselect for', existingProp.player);
                        }
                        
                        // Remove from selected props object and UI
                        delete selectedProps[existingPropId];
                        const existingElement = document.getElementById('prop-' + existingPropId);
                        if (existingElement) {
                            existingElement.remove();
                            console.log('Removed existing element from display');
                        }
                    }
                    
                    // Select the new prop
                    if (e.target.classList.contains('selected')) {
                        // If already selected, deselect it
                        e.target.classList.remove('selected');
                        delete selectedProps[propId];
                        document.getElementById('prop-' + propId)?.remove();
                    } else {
                        // Otherwise select it
                        if (Object.keys(selectedProps).length >= 8) {
                            alert('Maximum of 8 props allowed');
                            return;
                        }
                        
                        e.target.classList.add('selected');
                        selectedProps[propId] = propData;
                        
                        // Create selected prop display
                        const propElement = document.createElement('div');
                        propElement.id = 'prop-' + propId;
                        propElement.className = 'selected-prop-item';
                        propElement.innerHTML = `
                            <div>
                                <strong>${propData.player}</strong> (${propData.team})<br>
                                ${propData.display_stat}: ${propData.choice_display} ${propData.stat_value} (${propData.multiplier}x)
                            </div>
                            <span class="remove-prop" data-prop-id="${propId}">&times;</span>
                        `;
                        selectedPropsContainer.appendChild(propElement);
                        
                        // Scroll to the bottom of selected props to show the newly added item
                        selectedPropsContainer.scrollTop = selectedPropsContainer.scrollHeight;
                    }
                    
                    updateCombinedProbability();
                } else if (e.target.classList.contains('alt-button')) {
                    // Alt button logic remains the same
                    const overUnderId = e.target.dataset.overUnderId;
                    const altTargetId = e.target.dataset.altTarget;
                    const altContainer = document.getElementById(altTargetId);
                    const propData = JSON.parse(e.target.dataset.prop);
                    
                    // If already loaded, just toggle display
                    if (altContainer.dataset.loaded === 'true') {
                        if (altContainer.style.display === 'none' || !altContainer.style.display) {
                            altContainer.style.display = 'block';
                        } else {
                            altContainer.style.display = 'none';
                        }
                        return;
                    }
                    
                    // Mark as loading
                    altContainer.innerHTML = '<div class="text-center my-2"><div class="spinner-border spinner-border-sm" role="status"></div> Loading alternates...</div>';
                    altContainer.style.display = 'block';
                    
                    fetch(`https://api.underdogfantasy.com/v1/over_unders/${overUnderId}/alternate_projections`)
                        .then(response => {
                            if (!response.ok) {
                                throw new Error('Network response was not ok');
                            }
                            return response.json();
                        })
                        .then(data => {
                            // Create HTML for alternate props
                            let altPropsHtml = `<h6 class="mb-3">Alternate Lines</h6>`;
                            
                            data.projections.forEach(projection => {
                                altPropsHtml += `
                                    <div class="alt-prop-row">
                                        <span class="alt-prop-value">${projection.stat_value}</span>
                                        <div class="alt-prop-buttons">
                                            ${projection.options.map(option => {
                                                // Calculate probability for this option
                                                const playerName = propData.player.toLowerCase().replace(/\s+/g, '_').replace(/-/g, '#');
                                                const pitcherData = window.lookupData?.pitchers?.[playerName] || window.lookupData?.pitchers?.[propData.player] || window.lookupData?.pitchers?.[propData.player.toLowerCase()];
                                                const batterData = window.lookupData?.batters?.[playerName] || window.lookupData?.batters?.[propData.player] || window.lookupData?.batters?.[propData.player.toLowerCase()];
                                                const playerData = pitcherData || batterData;
                                                
                                                let probability = null;
                                                if (playerData && playerData[propData.stat_name]) {
                                                    const threshold = Math.ceil(parseFloat(projection.stat_value));
                                                    probability = playerData[propData.stat_name][threshold] || 0;
                                                    if (option.choice_id === 'under__') {
                                                        probability = 1 - probability;
                                                    }
                                                }
                                                
                                                // Create JSON data for the alt prop
                                                const altPropData = {
                                                    id: option.id,
                                                    options_id: option.id,
                                                    alt_id: true,
                                                    over_under_id: option.over_under_id,
                                                    player: propData.player,
                                                    team: propData.team,
                                                    stat_name: propData.stat_name,
                                                    display_stat: propData.display_stat,
                                                    stat_value: projection.stat_value,
                                                    type: option.choice_id,
                                                    choice_display: option.choice_display,
                                                    multiplier: option.payout_multiplier,
                                                    simulation_probability: probability
                                                };
                                                
                                                return `
                                                    <button class="alt-prop-button" 
                                                            data-prop='${JSON.stringify(altPropData)}'
                                                            data-prop-id="${altPropData.id}-${altPropData.type}">
                                                        ${option.choice_display} (${option.payout_multiplier}x)
                                                        ${probability !== null ? `
                                                            <span class="probability simulation-prob ${probability * option.payout_multiplier < 0.549 ? 'probability-red' : probability * option.payout_multiplier < 0.577 ? 'probability-yellow' : 'probability-green'}">
                                                                Sim: ${(probability * 100).toFixed(1)}%
                                                            </span>
                                                        ` : ''}
                                                    </button>
                                                `;
                                            }).join('')}
                                        </div>
                                    </div>
                                `;
                            });
                            
                            altContainer.innerHTML = altPropsHtml;
                            altContainer.dataset.loaded = 'true';
                        })
                        .catch(error => {
                            console.error('Error:', error);
                            altContainer.innerHTML = '<div class="alert alert-danger">Failed to load alternate props</div>';
                        });
                }
            });
        });
    </script>
</body>
</html> 