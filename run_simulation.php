<?php
require_once 'config.php';
require_once 'redis_helper.php';
require_once 'file_handler.php';
session_start();

// Debug logging
error_log("Run Simulation - Session ID: " . session_id());
error_log("Run Simulation - Session data: " . print_r($_SESSION, true));

// Increase memory limit and execution time for large simulations
ini_set('memory_limit', '1G');
ini_set('max_execution_time', 300); // 5 minutes
set_time_limit(300);

// Set header to return JSON
header('Content-Type: application/json');

// Check if it's an AJAX request
$isAjax = isset($_SERVER['HTTP_X_REQUESTED_WITH']) && $_SERVER['HTTP_X_REQUESTED_WITH'] === 'XMLHttpRequest';

// Handle file uploads if this is an AJAX request
if ($isAjax && $_SERVER['REQUEST_METHOD'] === 'POST') {
    try {
        $fileHandler = new FileHandler();
        $num_simulations = $_POST['num_simulations'] ?? 1000;
        
        // error_log("Processing AJAX upload for session: " . session_id());
        
        // Process hitter projections
        if (isset($_FILES['hitter_projections']) && $_FILES['hitter_projections']['error'] === UPLOAD_ERR_OK) {
            // error_log("Processing AJAX hitter file: " . $_FILES['hitter_projections']['name']);
            $hitter_path = $fileHandler->handleUpload($_FILES['hitter_projections'], session_id());
            // error_log("AJAX hitter file saved to: " . $hitter_path);
        }
        
        // Process pitcher projections
        if (isset($_FILES['pitcher_projections']) && $_FILES['pitcher_projections']['error'] === UPLOAD_ERR_OK) {
            // error_log("Processing AJAX pitcher file: " . $_FILES['pitcher_projections']['name']);
            $pitcher_path = $fileHandler->handleUpload($_FILES['pitcher_projections'], session_id());
            // error_log("AJAX pitcher file saved to: " . $pitcher_path);
        }
        
        // Store simulation parameters in session
        $_SESSION['simulation_params'] = [
            'num_simulations' => $num_simulations,
            'hitter_projections' => $hitter_path ?? null,
            'pitcher_projections' => $pitcher_path ?? null
        ];
        
        // error_log("AJAX session params stored: " . print_r($_SESSION['simulation_params'], true));
        
        // Run the simulation
        $python_script = __DIR__ . '/python/run_handler.py';
        $current_dir = __DIR__;
        $log_file = $current_dir . '/python_simulation.log';
        
        // Get absolute paths for the uploaded files
        $hitter_path = __DIR__ . '/' . $hitter_path;
        $pitcher_path = __DIR__ . '/' . $pitcher_path;
        
        // error_log("Constructed paths - Hitter: " . $hitter_path . ", Pitcher: " . $pitcher_path);
        
        // Verify files exist
        if (!file_exists($hitter_path) || !file_exists($pitcher_path)) {
            error_log("File check failed - Hitter exists: " . (file_exists($hitter_path) ? 'yes' : 'no') . 
                     ", Pitcher exists: " . (file_exists($pitcher_path) ? 'yes' : 'no'));
            throw new Exception('One or both files do not exist. Please try uploading again.');
        }
        
        // Execute the simulation handler
        $command = sprintf(
            'cd %s && PYTHONPATH=%s python3 %s %s %s %d > %s 2>&1',
            escapeshellarg($current_dir),
            escapeshellarg($current_dir),
            escapeshellarg($python_script),
            escapeshellarg($hitter_path),
            escapeshellarg($pitcher_path),
            $num_simulations,
            escapeshellarg($log_file)
        );
        
        // error_log("Executing command: " . $command);
        
        // Execute the command
        $output = [];
        $return_var = 0;
        exec($command, $output, $return_var);
        
        // error_log("Command output: " . print_r($output, true));
        // error_log("Command return var: " . $return_var);
        
        // Read the log file
        $log_content = file_exists($log_file) ? file_get_contents($log_file) : '';
        // error_log("Python log content: " . $log_content);
        
        if ($return_var !== 0) {
            throw new Exception('Simulation failed: ' . $log_content);
        }
        
        // Clean up files
        $fileHandler->cleanupUserFiles(session_id());
        // error_log("Cleaned up files for session: " . session_id());
        
        echo json_encode([
            'success' => true,
            'message' => 'Simulation completed successfully!',
            'log' => $log_content
        ]);
        exit;
    } catch (Exception $e) {
        error_log("AJAX error: " . $e->getMessage());
        echo json_encode(['success' => false, 'error' => $e->getMessage()]);
        exit;
    }
}

// If we get here, it's not an AJAX request
echo json_encode(['success' => false, 'error' => 'Invalid request']);
exit; 