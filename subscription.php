<?php
require __DIR__ . '/headers.php';
require_once 'config.php';
require_once 'subscription_helper.php';

session_start();

// Debug info for development
if (isset($_GET['success']) && $_SERVER['HTTP_HOST'] === 'localhost:8000') {
    error_log("Subscription success page accessed. Session user_id: " . ($_SESSION['user_id'] ?? 'NOT SET'));
    error_log("Session data: " . print_r($_SESSION, true));
}

// Check if user is logged in
if (!isset($_SESSION['user_id'])) {
    header('Location: index.php?error=login_required');
    exit;
}

$subscriptionHelper = new SubscriptionHelper();
$userId = $_SESSION['user_id'];
$userSubscription = $subscriptionHelper->getUserSubscription($userId);
$simulationLimit = $subscriptionHelper->getSimulationLimit($userId);

// Handle subscription actions
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $action = $_POST['action'] ?? '';
    
    try {
        switch ($action) {
            case 'subscribe_weekly':
                // Determine if we're on localhost for development
                $protocol = (isset($_SERVER['HTTPS']) && $_SERVER['HTTPS'] === 'on') || $_SERVER['SERVER_PORT'] == 443 ? 'https' : 'http';
                if ($_SERVER['HTTP_HOST'] === 'localhost:8000') {
                    $protocol = 'http'; // Force HTTP for localhost development
                }
                
                $session = $subscriptionHelper->createCheckoutSession(
                    $userId,
                    'price_1RWJVWQSCNdWM7EjvBVl9o7U', // Your weekly price ID
                    $protocol . '://' . $_SERVER['HTTP_HOST'] . '/subscription.php?success=1',
                    $protocol . '://' . $_SERVER['HTTP_HOST'] . '/subscription.php?canceled=1'
                );
                header('Location: ' . $session->url);
                exit;
                
            case 'manage_subscription':
                // Determine if we're on localhost for development
                $protocol = (isset($_SERVER['HTTPS']) && $_SERVER['HTTPS'] === 'on') || $_SERVER['SERVER_PORT'] == 443 ? 'https' : 'http';
                if ($_SERVER['HTTP_HOST'] === 'localhost:8000') {
                    $protocol = 'http'; // Force HTTP for localhost development
                }
                
                $portalSession = $subscriptionHelper->createPortalSession(
                    $userId,
                    $protocol . '://' . $_SERVER['HTTP_HOST'] . '/subscription.php'
                );
                header('Location: ' . $portalSession->url);
                exit;
        }
    } catch (Exception $e) {
        $error = $e->getMessage();
    }
}

$success = $_GET['success'] ?? null;
$canceled = $_GET['canceled'] ?? null;
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Subscription - Sweating Pickems</title>
    <link rel="apple-touch-icon" sizes="180x180" href="favicon/apple-touch-icon.png">
    <link rel="icon" type="image/png" sizes="32x32" href="favicon/favicon-32x32.png">
    <link rel="icon" type="image/png" sizes="16x16" href="favicon/favicon-16x16.png">
    <link rel="manifest" href="favicon/site.webmanifest">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="css/style.css" rel="stylesheet">
</head>
<body>
    <?php include 'header.php'; ?>

    <div class="container mt-4">
        <h1>Subscription Management</h1>
        
        <?php if ($success): ?>
            <div class="alert alert-success">
                <h4>Welcome to Premium!</h4>
                <p>Your subscription has been activated successfully. You can now run up to <?php echo number_format(PREMIUM_SIMULATION_LIMIT); ?> simulations!</p>
            </div>
        <?php endif; ?>
        
        <?php if ($canceled): ?>
            <div class="alert alert-warning">
                <p>Subscription canceled. You can still subscribe anytime to unlock premium features.</p>
            </div>
        <?php endif; ?>
        
        <?php if (isset($error)): ?>
            <div class="alert alert-danger">
                <p>Error: <?php echo htmlspecialchars($error); ?></p>
            </div>
        <?php endif; ?>

        <div class="row">
            <div class="col-lg-8">
                <?php if ($userSubscription && $userSubscription['is_active']): ?>
                    <!-- Active Subscription -->
                    <div class="card mb-4">
                        <div class="card-header bg-success text-white">
                            <h5 class="mb-0">Premium Subscription Active</h5>
                        </div>
                        <div class="card-body">
                            <div class="row">
                                <div class="col-md-6">
                                    <p><strong>Status:</strong> <span class="badge bg-success">Active</span></p>
                                    <p><strong>Simulation Limit:</strong> <?php echo number_format($simulationLimit); ?> per upload</p>
                                    <p><strong>Next Billing Date:</strong> <?php echo date('F j, Y', $userSubscription['current_period_end']); ?></p>
                                </div>
                                <div class="col-md-6">
                                    <?php if ($userSubscription['cancel_at_period_end']): ?>
                                        <div class="alert alert-warning">
                                            <strong>Subscription Ending:</strong> Your subscription will end on <?php echo date('F j, Y', $userSubscription['current_period_end']); ?>
                                        </div>
                                    <?php endif; ?>
                                </div>
                            </div>
                            <form method="POST">
                                <input type="hidden" name="action" value="manage_subscription">
                                <button type="submit" class="btn btn-primary">Manage Subscription</button>
                            </form>
                        </div>
                    </div>
                <?php else: ?>
                    <!-- No Active Subscription -->
                    <div class="row justify-content-center">
                        <div class="col-md-8">
                            <div class="card mb-4 border-primary">
                                <div class="card-header bg-primary text-white text-center">
                                    <h4 class="mb-0"><i class="bi bi-star-fill"></i> Premium Weekly</h4>
                                </div>
                                <div class="card-body text-center">
                                    <div class="mb-4">
                                        <h1 class="text-primary">$9.97<small class="text-muted fs-5">/week</small></h1>
                                        <p class="text-muted">Perfect for active bettors</p>
                                    </div>
                                    
                                    <div class="row text-start mb-4">
                                        <div class="col-md-6">
                                            <ul class="list-unstyled">
                                                <li class="mb-2"><i class="bi bi-check-circle text-success"></i> Up to <?php echo number_format(PREMIUM_SIMULATION_LIMIT); ?> simulations per upload</li>
                                                <li class="mb-2"><i class="bi bi-check-circle text-success"></i> Email support</li>
                                            </ul>
                                        </div>
                                        <div class="col-md-6">
                                            <ul class="list-unstyled">
                                                <li class="mb-2"><i class="bi bi-check-circle text-success"></i> Cancel anytime</li>
                                                <li class="mb-2"><i class="bi bi-check-circle text-success"></i> Instant activation</li>
                                            </ul>
                                        </div>
                                    </div>
                                    
                                    <form method="POST">
                                        <input type="hidden" name="action" value="subscribe_weekly">
                                        <button type="submit" class="btn btn-primary btn-lg px-5">Subscribe Now</button>
                                    </form>
                                    
                                    <p class="text-muted small mt-3">
                                        Weekly billing. Cancel anytime through your account portal.<br>
                                        7-day commitment, then renews automatically.
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                <?php endif; ?>
            </div>
            
            <div class="col-lg-4">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">Current Usage</h5>
                    </div>
                    <div class="card-body">
                        <p><strong>Current Plan:</strong> <?php echo $userSubscription && $userSubscription['is_active'] ? 'Premium' : 'Free'; ?></p>
                        <p><strong>Simulation Limit:</strong> <?php echo number_format($simulationLimit); ?> per upload</p>
                        
                        <?php if (!$userSubscription || !$userSubscription['is_active']): ?>
                            <div class="alert alert-info">
                                <small>Free users are limited to <?php echo number_format(FREE_SIMULATION_LIMIT); ?> simulations per upload. Upgrade to Premium for up to 10,000 sims at a time!</small>
                            </div>
                        <?php endif; ?>
                    </div>
                </div>
                
                <div class="card mt-4">
                    <div class="card-header">
                        <h5 class="mb-0">Need Help?</h5>
                    </div>
                    <div class="card-body">
                        <p>Questions about your subscription?</p>
                        <a href="mailto:aidanhall21@gmail.com" class="btn btn-outline-primary btn-sm">Contact Support</a>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.7.2/font/bootstrap-icons.css">
</body>
</html> 