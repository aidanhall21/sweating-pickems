<?php
require __DIR__ . '/headers.php';
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sweating Pickems</title>
    <link rel="apple-touch-icon" sizes="180x180" href="favicon/apple-touch-icon.png">
    <link rel="icon" type="image/png" sizes="32x32" href="favicon/favicon-32x32.png">
    <link rel="icon" type="image/png" sizes="16x16" href="favicon/favicon-16x16.png">
    <link rel="manifest" href="favicon/site.webmanifest">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="css/style.css" rel="stylesheet">
</head>
<body>
    <?php include 'header.php'; 
    $isLoggedIn = isset($_SESSION['user_id']);
    ?>

    <div class="container mt-4">
        <h1>Welcome to Sweating Pickems</h1>
        <p>This tool lets you turn your MLB projections into probability distributions using proprietary play-by-play simulation models.</p>
        <p>Compare simulated outcomes to Underdog player props to find positive expected value bets.</p>
        
        <div class="row mt-4">
            <div class="col-md-4">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">Upload Projections</h5>
                        <p class="card-text">Upload your CSV files containing player projections for hitters and pitchers.</p>
                        <a href="upload.php" class="btn btn-primary">Go to Upload</a>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">View Props</h5>
                        <p class="card-text">Browse and analyze available props from Underdog.</p>
                        <a href="props.php" class="btn btn-primary">View Props</a>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card border-primary">
                    <div class="card-header bg-primary text-white">
                        <h5 class="card-title mb-0"><i class="bi bi-star-fill"></i> Premium Weekly</h5>
                    </div>
                    <div class="card-body">
                        <div class="text-center mb-3">
                            <h4 class="text-primary">$9.97<small class="text-muted">/week</small></h4>
                        </div>
                        <ul class="list-unstyled">
                            <li><i class="bi bi-check-circle text-success"></i> Up to 10,000 simulations per upload</li>
                            <li><i class="bi bi-check-circle text-success"></i> Email support</li>
                            <li><i class="bi bi-check-circle text-success"></i> Cancel anytime</li>
                        </ul>
                        <p class="card-text text-muted">
                            <small>Free users: 250 simulations max<br>
                            Weekly billing, flexible cancellation</small>
                        </p>
                        <?php if ($isLoggedIn): ?>
                            <a href="subscription.php" class="btn btn-primary">Subscribe Now</a>
                        <?php else: ?>
                            <button onclick="handleSubscribeClick()" class="btn btn-primary">Subscribe Now</button>
                            <p class="text-muted small mt-2">
                                <i class="bi bi-info-circle"></i> Login required to subscribe
                            </p>
                        <?php endif; ?>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="row mt-4">
            <div class="col-12">
                <div class="card bg-light">
                    <div class="card-body">
                        <h5 class="card-title">How It Works</h5>
                        <div class="row">
                            <div class="col-md-3 text-center mb-3">
                                <div class="display-6 text-primary mb-2">1</div>
                                <h6>Upload Projections</h6>
                                <p class="small text-muted">Upload your hitter and pitcher projection files</p>
                            </div>
                            <div class="col-md-3 text-center mb-3">
                                <div class="display-6 text-primary mb-2">2</div>
                                <h6>Run Simulations</h6>
                                <p class="small text-muted">Our models simulate thousands of games based on your projections</p>
                            </div>
                            <div class="col-md-3 text-center mb-3">
                                <div class="display-6 text-primary mb-2">3</div>
                                <h6>Compare Props</h6>
                                <p class="small text-muted">View Underdog props alongside simulation probabilities</p>
                            </div>
                            <div class="col-md-3 text-center mb-3">
                                <div class="display-6 text-primary mb-2">4</div>
                                <h6>Find Value</h6>
                                <p class="small text-muted">Identify positive expected value betting opportunities</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.7.2/font/bootstrap-icons.css">
    <script>
        function handleSubscribeClick() {
            if (confirm('You need to sign in with Google first to subscribe. Would you like to sign in now?')) {
                loginWithGoogle();
            }
        }
    </script>
</body>
</html> 