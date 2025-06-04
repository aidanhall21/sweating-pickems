<?php
require __DIR__ . '/vendor/autoload.php';
require __DIR__ . '/headers.php';

use Firebase\JWT\JWT;
use Firebase\JWT\JWK;
use Firebase\JWT\Key;

// Set headers for JSON response
header('Content-Type: application/json');

// Only allow POST requests
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(["error" => "Method not allowed"]);
    exit;
}

// Get token from client
$input = json_decode(file_get_contents("php://input"), true);
$token = $input["token"] ?? "";

if (empty($token)) {
    http_response_code(400);
    echo json_encode(["error" => "No token provided"]);
    exit;
}

// Get Google public keys with caching
$cacheFile = __DIR__ . '/google_keys.cache';
$cacheTime = 3600; // 1 hour

if (file_exists($cacheFile) && (time() - filemtime($cacheFile) < $cacheTime)) {
    $keys = json_decode(file_get_contents($cacheFile), true);
} else {
    $keys = json_decode(file_get_contents('https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com'), true);
    file_put_contents($cacheFile, json_encode($keys));
}

try {
    // Get the key ID from the token header
    $tokenParts = explode('.', $token);
    if (count($tokenParts) !== 3) {
        throw new Exception('Invalid token format');
    }
    
    $header = json_decode(base64_decode($tokenParts[0]), true);
    $kid = $header['kid'] ?? null;
    
    if (!$kid) {
        throw new Exception('No key ID in token');
    }
    
    $key = $keys[$kid] ?? null;
    if (!$key) {
        throw new Exception('Key not found');
    }

    // Decode and verify the token
    $decoded = JWT::decode($token, new Key($key, 'RS256'));
    
    // Verify the token is not expired
    if ($decoded->exp < time()) {
        throw new Exception('Token has expired');
    }
    
    // Verify the token was issued by the correct project
    if ($decoded->aud !== 'sweating-pickems') {
        throw new Exception('Invalid audience');
    }

    // Verify the token was issued by the correct issuer
    if ($decoded->iss !== 'https://securetoken.google.com/sweating-pickems') {
        throw new Exception('Invalid issuer');
    }
    
    // Start session and store user data
    session_start();
    $_SESSION['user_id'] = $decoded->sub;
    $_SESSION['email'] = $decoded->email ?? null;
    $_SESSION['name'] = $decoded->name ?? null;
    $_SESSION['picture'] = $decoded->picture ?? null;
    $_SESSION['auth_time'] = $decoded->auth_time ?? null;
    $_SESSION['firebase'] = [
        'sign_in_provider' => $decoded->firebase->sign_in_provider ?? null,
        'tenant' => $decoded->firebase->tenant ?? null
    ];
    
    // Return success with user data
    echo json_encode([
        "success" => true,
        "user" => [
            "uid" => $decoded->sub,
            "email" => $decoded->email ?? null,
            "name" => $decoded->name ?? null,
            "picture" => $decoded->picture ?? null,
            "auth_time" => $decoded->auth_time ?? null,
            "firebase" => [
                "sign_in_provider" => $decoded->firebase->sign_in_provider ?? null,
                "tenant" => $decoded->firebase->tenant ?? null
            ]
        ]
    ]);
    
} catch (Exception $e) {
    http_response_code(401);
    echo json_encode([
        "error" => "Authentication failed",
        "message" => $e->getMessage()
    ]);
}
?>