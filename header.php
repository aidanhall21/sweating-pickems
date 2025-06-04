<?php
require __DIR__ . '/headers.php';
session_start();
$isLoggedIn = isset($_SESSION['user_id']);
$userName = $_SESSION['name'] ?? '';

// Get subscription status for display
if ($isLoggedIn) {
    require_once 'subscription_helper.php';
    $subscriptionHelper = new SubscriptionHelper();
    $hasActiveSubscription = $subscriptionHelper->hasActiveSubscription($_SESSION['user_id']);
} else {
    $hasActiveSubscription = false;
}
?>
<nav class="navbar navbar-expand-lg navbar-dark bg-dark">
    <div class="container">
        <a class="navbar-brand" href="index.php">Sweating Pickems</a>
        <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
            <span class="navbar-toggler-icon"></span>
        </button>
        <div class="collapse navbar-collapse" id="navbarNav">
            <ul class="navbar-nav me-auto">
                <li class="nav-item">
                    <a class="nav-link" href="upload.php">Upload Projections</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" href="props.php">View Props</a>
                </li>
                <?php if ($isLoggedIn): ?>
                    <li class="nav-item">
                        <a class="nav-link" href="subscription.php">
                            Subscription
                            <?php if ($hasActiveSubscription): ?>
                                <span class="badge bg-success ms-1">Premium</span>
                            <?php endif; ?>
                        </a>
                    </li>
                <?php endif; ?>
            </ul>
            <div class="d-flex align-items-center">
                <div id="user-info" class="me-3 <?php echo $isLoggedIn ? '' : 'd-none'; ?>">
                    <span class="text-light" id="user-name"><?php echo htmlspecialchars($userName); ?></span>
                    <?php if ($hasActiveSubscription): ?>
                        <span class="badge bg-success ms-2">Premium</span>
                    <?php endif; ?>
                </div>
                <div id="auth-buttons">
                    <button id="login-button" class="btn btn-outline-light <?php echo $isLoggedIn ? 'd-none' : ''; ?>" onclick="loginWithGoogle()">
                        <i class="bi bi-google me-2"></i>Sign in with Google
                    </button>
                    <button id="logout-button" class="btn btn-outline-light <?php echo $isLoggedIn ? '' : 'd-none'; ?>" onclick="logout()">
                        <i class="bi bi-box-arrow-right me-2"></i>Logout
                    </button>
                </div>
            </div>
        </div>
    </div>
</nav>

<!-- Required scripts for authentication -->
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.7.2/font/bootstrap-icons.css">
<script type="module" src="auth.js"></script> 