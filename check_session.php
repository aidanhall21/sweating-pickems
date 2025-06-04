<?php
session_start();
header('Content-Type: application/json');

// Check if user is logged in based on session data
$isLoggedIn = isset($_SESSION['user_id']);

// Return the login status
echo json_encode([
    'isLoggedIn' => $isLoggedIn,
    'userId' => $isLoggedIn ? $_SESSION['user_id'] : null,
    'name' => $isLoggedIn ? $_SESSION['name'] : null
]);
?> 