<?php
require_once 'config.php';
require_once 'subscription_helper.php';

session_start();
header('Content-Type: application/json');

$subscriptionHelper = new SubscriptionHelper();
$userId = $_SESSION['user_id'] ?? null;
$isLoggedIn = $userId !== null;

if ($isLoggedIn) {
    $hasActiveSubscription = $subscriptionHelper->hasActiveSubscription($userId);
    $simulationLimit = $subscriptionHelper->getSimulationLimit($userId);
} else {
    $hasActiveSubscription = false;
    $simulationLimit = FREE_SIMULATION_LIMIT;
}

echo json_encode([
    'isLoggedIn' => $isLoggedIn,
    'hasActiveSubscription' => $hasActiveSubscription,
    'simulationLimit' => $simulationLimit,
    'userId' => $userId,
    'name' => $_SESSION['name'] ?? null
]);
?> 