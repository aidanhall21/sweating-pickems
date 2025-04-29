<?php
class FileHandler {
    private $uploadBaseDir;
    private $maxFileSize = 10485760; // 10MB
    private $allowedTypes = ['text/csv', 'application/vnd.ms-excel'];
    
    public function __construct() {
        // Set upload directory to be inside the project directory
        $this->uploadBaseDir = __DIR__ . '/uploads';
        if (!file_exists($this->uploadBaseDir)) {
            mkdir($this->uploadBaseDir, 0755, true);
        }
    }
    
    public function handleUpload($file, $sessionId) {
        // Validate file
        if (!$this->validateFile($file)) {
            throw new Exception('Invalid file');
        }
        
        // Create user-specific directory
        $userDir = $this->uploadBaseDir . '/' . $sessionId;
        if (!file_exists($userDir)) {
            mkdir($userDir, 0755, true);
        }
        
        // Generate unique filename
        $extension = pathinfo($file['name'], PATHINFO_EXTENSION);
        $filename = uniqid() . '.' . $extension;
        $filepath = $userDir . '/' . $filename;
        
        // Move file
        if (!move_uploaded_file($file['tmp_name'], $filepath)) {
            throw new Exception('Failed to move uploaded file');
        }
        
        // Return relative path from project root
        return 'uploads/' . $sessionId . '/' . $filename;
    }
    
    private function validateFile($file) {
        // Check file size
        if ($file['size'] > $this->maxFileSize) {
            return false;
        }
        
        // Check file type
        if (!in_array($file['type'], $this->allowedTypes)) {
            return false;
        }
        
        // Additional validation can be added here
        
        return true;
    }
    
    public function cleanupUserFiles($sessionId) {
        $userDir = $this->uploadBaseDir . '/' . $sessionId;
        if (file_exists($userDir)) {
            $files = glob($userDir . '/*');
            foreach ($files as $file) {
                if (is_file($file)) {
                    unlink($file);
                }
            }
            rmdir($userDir);
        }
    }
    
    public function cleanupOldFiles($maxAge = 3600) { // 1 hour
        $files = glob($this->uploadBaseDir . '/*/*');
        $now = time();
        
        foreach ($files as $file) {
            if (is_file($file)) {
                if ($now - filemtime($file) >= $maxAge) {
                    unlink($file);
                }
            }
        }
        
        // Remove empty directories
        $dirs = glob($this->uploadBaseDir . '/*', GLOB_ONLYDIR);
        foreach ($dirs as $dir) {
            if (count(glob($dir . '/*')) === 0) {
                rmdir($dir);
            }
        }
    }
} 