<?php
require_once 'config.php';
require_once 'subscription_helper.php';

// Set headers
header('Content-Type: application/json');

// Only allow POST requests
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['error' => 'Method not allowed']);
    exit;
}

// Get the raw payload
$payload = file_get_contents('php://input');
$signature = $_SERVER['HTTP_STRIPE_SIGNATURE'] ?? '';

if (empty($signature)) {
    http_response_code(400);
    echo json_encode(['error' => 'Missing signature']);
    exit;
}

try {
    $subscriptionHelper = new SubscriptionHelper();
    $success = $subscriptionHelper->handleWebhook($payload, $signature);
    
    if ($success) {
        http_response_code(200);
        echo json_encode(['success' => true]);
    } else {
        http_response_code(400);
        echo json_encode(['error' => 'Webhook processing failed']);
    }
} catch (Exception $e) {
    error_log('Webhook error: ' . $e->getMessage());
    http_response_code(400);
    echo json_encode(['error' => 'Webhook processing failed']);
}
?> 