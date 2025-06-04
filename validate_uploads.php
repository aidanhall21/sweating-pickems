<?php
require_once 'config.php';
require_once 'file_handler.php';
session_start();

// Set header to return JSON
header('Content-Type: application/json');

/**
 * Validates uploaded files before running simulations
 */
function validateUploads($hitterPath, $pitcherPath) {
    // Get absolute paths
    $hitterAbsPath = __DIR__ . '/' . $hitterPath;
    $pitcherAbsPath = __DIR__ . '/' . $pitcherPath;
    
    // Check if files exist
    if (!file_exists($hitterAbsPath) || !file_exists($pitcherAbsPath)) {
        return [
            'success' => false,
            'message' => 'One or both files do not exist. Please try uploading again.'
        ];
    }
    
    // Call Python validation script
    $python_script = __DIR__ . '/python/validate_uploads.py';
    $current_dir = __DIR__;
    $log_file = $current_dir . '/validation.log';
    
    $command = sprintf(
        'cd %s && %s/venv/bin/python3 %s %s %s 2>&1',
        escapeshellarg($current_dir),
        escapeshellarg($current_dir),
        escapeshellarg($python_script),
        escapeshellarg($hitterAbsPath),
        escapeshellarg($pitcherAbsPath)
    );
    
    error_log("Executing validation command: " . $command);
    
    $output = [];
    $return_var = 0;
    exec($command, $output, $return_var);
    
    error_log("Validation output: " . print_r($output, true));
    error_log("Validation return var: " . $return_var);
    
    // Parse output as JSON
    $jsonOutput = implode('', $output);
    $result = json_decode($jsonOutput, true);
    
    if ($result === null) {
        return [
            'success' => false,
            'message' => 'Error validating files: Unable to parse validation results',
            'log' => implode("\n", $output)
        ];
    }
    
    return [
        'success' => $result['valid'],
        'message' => $result['message'],
        'details' => $result['details'] ?? null
    ];
}

// Handle AJAX validation request
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    try {
        // Process file uploads if not already processed
        $fileHandler = new FileHandler();
        $hitter_path = null;
        $pitcher_path = null;
        
        // Process hitter projections
        if (isset($_FILES['hitter_projections']) && $_FILES['hitter_projections']['error'] === UPLOAD_ERR_OK) {
            $hitter_path = $fileHandler->handleUpload($_FILES['hitter_projections'], session_id());
        } else if (isset($_POST['hitter_path'])) {
            // Use path provided in request
            $hitter_path = $_POST['hitter_path'];
        } else {
            throw new Exception('No hitter projections file provided');
        }
        
        // Process pitcher projections
        if (isset($_FILES['pitcher_projections']) && $_FILES['pitcher_projections']['error'] === UPLOAD_ERR_OK) {
            $pitcher_path = $fileHandler->handleUpload($_FILES['pitcher_projections'], session_id());
        } else if (isset($_POST['pitcher_path'])) {
            // Use path provided in request
            $pitcher_path = $_POST['pitcher_path'];
        } else {
            throw new Exception('No pitcher projections file provided');
        }
        
        // Validate the files
        $validation_result = validateUploads($hitter_path, $pitcher_path);
        
        if (!$validation_result['success']) {
            echo json_encode([
                'success' => false,
                'error' => $validation_result['message'],
                'details' => $validation_result['details'] ?? null
            ]);
            exit;
        }
        
        // Store validated paths in session
        $_SESSION['simulation_params'] = [
            'num_simulations' => $_POST['num_simulations'] ?? 1000,
            'hitter_projections' => $hitter_path,
            'pitcher_projections' => $pitcher_path,
            'validated' => true
        ];
        
        echo json_encode([
            'success' => true,
            'message' => 'Files validated successfully',
            'hitter_path' => $hitter_path,
            'pitcher_path' => $pitcher_path
        ]);
        exit;
        
    } catch (Exception $e) {
        error_log("Validation error: " . $e->getMessage());
        echo json_encode([
            'success' => false,
            'error' => $e->getMessage()
        ]);
        exit;
    }
}

// If not a POST request, return error
echo json_encode([
    'success' => false,
    'error' => 'Invalid request method'
]);
exit; 