<?php
require_once 'file_handler.php';

// Set error logging
ini_set('log_errors', 1);
ini_set('error_log', dirname(__FILE__) . '/cleanup.log');

try {
    $fileHandler = new FileHandler();
    
    // Clean up files older than 24 hours
    $fileHandler->cleanupOldFiles(86400);
    
    // Log successful cleanup
    error_log("Cleanup completed successfully at " . date('Y-m-d H:i:s'));
} catch (Exception $e) {
    // Log any errors
    error_log("Cleanup failed: " . $e->getMessage());
} 