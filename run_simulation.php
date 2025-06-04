<?php
require_once 'config.php';
require_once 'redis_helper.php';
require_once 'file_handler.php';
session_start();

// Debug logging
error_log("Run Simulation - Session ID: " . session_id());
error_log("Run Simulation - Session data: " . print_r($_SESSION, true));

// Increase memory limit and execution time for large simulations
ini_set('memory_limit', '2G');  // Increased memory limit
ini_set('max_execution_time', 600); // 10 minutes
set_time_limit(600);

// Set process priority to improve performance
if (function_exists('proc_nice')) {
    proc_nice(-10);  // Higher priority for the simulation process
}

// Enable output buffering to reduce I/O overhead
ob_start();

// Set CPU affinity if available (Linux only)
if (function_exists('pcntl_setaffinity')) {
    pcntl_setaffinity([0, 1]); // Use both CPUs
}

// Set header to return JSON
header('Content-Type: application/json');

// Check if it's an AJAX request
$isAjax = isset($_SERVER['HTTP_X_REQUESTED_WITH']) && $_SERVER['HTTP_X_REQUESTED_WITH'] === 'XMLHttpRequest';

// Handle file uploads if this is an AJAX request
if ($isAjax && $_SERVER['REQUEST_METHOD'] === 'POST') {
    try {
        $fileHandler = new FileHandler();
        $num_simulations = $_POST['num_simulations'] ?? 1000;
        
        error_log("Processing AJAX upload for session: " . session_id());
        error_log("Number of simulations requested: " . $num_simulations);
        
        // Check if we're using pre-validated paths from the session
        $useValidatedPaths = false;
        
        // Process hitter projections
        if (isset($_FILES['hitter_projections']) && $_FILES['hitter_projections']['error'] === UPLOAD_ERR_OK) {
            error_log("Processing AJAX hitter file: " . $_FILES['hitter_projections']['name']);
            $hitter_path = $fileHandler->handleUpload($_FILES['hitter_projections'], session_id());
            error_log("AJAX hitter file saved to: " . $hitter_path);
        } else if (isset($_POST['hitter_path'])) {
            // Use path provided in request (from validation)
            $hitter_path = $_POST['hitter_path'];
            error_log("Using provided hitter path: " . $hitter_path);
            $useValidatedPaths = true;
        } else {
            error_log("Hitter file upload error: " . ($_FILES['hitter_projections']['error'] ?? 'No file uploaded'));
        }
        
        // Process pitcher projections
        if (isset($_FILES['pitcher_projections']) && $_FILES['pitcher_projections']['error'] === UPLOAD_ERR_OK) {
            error_log("Processing AJAX pitcher file: " . $_FILES['pitcher_projections']['name']);
            $pitcher_path = $fileHandler->handleUpload($_FILES['pitcher_projections'], session_id());
            error_log("AJAX pitcher file saved to: " . $pitcher_path);
        } else if (isset($_POST['pitcher_path'])) {
            // Use path provided in request (from validation)
            $pitcher_path = $_POST['pitcher_path'];
            error_log("Using provided pitcher path: " . $pitcher_path);
            $useValidatedPaths = true;
        } else {
            error_log("Pitcher file upload error: " . ($_FILES['pitcher_projections']['error'] ?? 'No file uploaded'));
        }
        
        // Store simulation parameters in session if not already validated
        if (!$useValidatedPaths) {
            $_SESSION['simulation_params'] = [
                'num_simulations' => $num_simulations,
                'hitter_projections' => $hitter_path ?? null,
                'pitcher_projections' => $pitcher_path ?? null
            ];
            
            error_log("AJAX session params stored: " . print_r($_SESSION['simulation_params'], true));
            
            // If not validated and not using files directly from the form, validate now
            if (!isset($_SESSION['simulation_params']['validated']) && !isset($_FILES['hitter_projections'])) {
                // Files haven't been validated yet, redirect to validation
                echo json_encode([
                    'success' => false,
                    'error' => 'Files need to be validated first'
                ]);
                exit;
            }
        }
        
        // Run the simulation
        $python_script = __DIR__ . '/python/run_handler.py';
        $current_dir = __DIR__;
        $log_file = $current_dir . '/python_simulation.log';
        
        error_log("Python script path: " . $python_script);
        error_log("Current directory: " . $current_dir);
        error_log("Log file path: " . $log_file);
        
        // Get absolute paths for the uploaded files
        $hitter_path = __DIR__ . '/' . $hitter_path;
        $pitcher_path = __DIR__ . '/' . $pitcher_path;
        
        error_log("Constructed paths - Hitter: " . $hitter_path . ", Pitcher: " . $pitcher_path);
        
        // Verify files exist
        if (!file_exists($hitter_path) || !file_exists($pitcher_path)) {
            error_log("File check failed - Hitter exists: " . (file_exists($hitter_path) ? 'yes' : 'no') . 
                     ", Pitcher exists: " . (file_exists($pitcher_path) ? 'yes' : 'no'));
            throw new Exception('One or both files do not exist. Please try uploading again.');
        }
        
        // Execute the simulation handler with optimized environment variables
        $command = sprintf(
            'cd %s && PYTHONPATH=%s OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 %s/venv/bin/python3 -O %s %s %s %d > %s 2>&1',
            escapeshellarg($current_dir),
            escapeshellarg($current_dir),
            escapeshellarg($current_dir),
            escapeshellarg($python_script),
            escapeshellarg($hitter_path),
            escapeshellarg($pitcher_path),
            $num_simulations,
            escapeshellarg($log_file)
        );
        
        error_log("Executing command: " . $command);
        
        // Execute the command
        $output = [];
        $return_var = 0;
        exec($command, $output, $return_var);
        
        error_log("Command output: " . print_r($output, true));
        error_log("Command return var: " . $return_var);
        
        // Read the log file
        $log_content = file_exists($log_file) ? file_get_contents($log_file) : '';
        error_log("Python log content: " . $log_content);
        
        if ($return_var !== 0) {
            throw new Exception('Simulation failed: ' . $log_content);
        }
        
        // Clean up files
        $fileHandler->cleanupUserFiles(session_id());
        error_log("Cleaned up files for session: " . session_id());
        
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