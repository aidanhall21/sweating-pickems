<?php
require_once 'config.php';
require_once 'file_handler.php';
require_once 'subscription_helper.php';
session_start();

// Debug logging
error_log("Session ID: " . session_id());
error_log("Session data: " . print_r($_SESSION, true));

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // Only handle direct POST requests, not AJAX requests
    if (!isset($_SERVER['HTTP_X_REQUESTED_WITH']) || $_SERVER['HTTP_X_REQUESTED_WITH'] !== 'XMLHttpRequest') {
        try {
            $fileHandler = new FileHandler();
            $subscriptionHelper = new SubscriptionHelper();
            $num_simulations = $_POST['num_simulations'] ?? 1000;
            
            // Get simulation limit based on subscription status
            $userId = $_SESSION['user_id'] ?? null;
            $max_sims = $userId ? $subscriptionHelper->getSimulationLimit($userId) : FREE_SIMULATION_LIMIT;
            
            if ($num_simulations > $max_sims) {
                $hasSubscription = $userId ? $subscriptionHelper->hasActiveSubscription($userId) : false;
                if (!$userId) {
                    throw new Exception("Maximum number of simulations exceeded. Please log in to access more simulations.");
                } elseif (!$hasSubscription) {
                    throw new Exception("Maximum number of simulations exceeded. Upgrade to Premium to run up to " . number_format(PREMIUM_SIMULATION_LIMIT) . " simulations.");
                } else {
                    throw new Exception("Maximum number of simulations exceeded. Premium limit is " . number_format(PREMIUM_SIMULATION_LIMIT) . " simulations.");
                }
            }
            
            error_log("Processing upload for session: " . session_id());
            
            // Process hitter projections
            if (isset($_FILES['hitter_projections']) && $_FILES['hitter_projections']['error'] === UPLOAD_ERR_OK) {
                error_log("Processing hitter file: " . $_FILES['hitter_projections']['name']);
                $hitter_path = $fileHandler->handleUpload($_FILES['hitter_projections'], session_id());
                error_log("Hitter file saved to: " . $hitter_path);
            }
            
            // Process pitcher projections
            if (isset($_FILES['pitcher_projections']) && $_FILES['pitcher_projections']['error'] === UPLOAD_ERR_OK) {
                error_log("Processing pitcher file: " . $_FILES['pitcher_projections']['name']);
                $pitcher_path = $fileHandler->handleUpload($_FILES['pitcher_projections'], session_id());
                error_log("Pitcher file saved to: " . $pitcher_path);
            }
            
            // Store simulation parameters in session
            $_SESSION['simulation_params'] = [
                'num_simulations' => $num_simulations,
                'hitter_projections' => $hitter_path ?? null,
                'pitcher_projections' => $pitcher_path ?? null
            ];
            
            error_log("Session params stored: " . print_r($_SESSION['simulation_params'], true));
            
            // Redirect to simulation results page
            header('Location: run_simulation.php');
            exit;
        } catch (Exception $e) {
            error_log("Upload error: " . $e->getMessage());
            $_SESSION['error'] = $e->getMessage();
            header('Location: upload.php?error=1');
            exit;
        }
    }
}

// Clean up old files periodically (every 100 requests)
if (rand(1, 100) === 1) {
    $fileHandler = new FileHandler();
    $fileHandler->cleanupOldFiles();
}

// Get current user's simulation limit for display
$subscriptionHelper = new SubscriptionHelper();
$userId = $_SESSION['user_id'] ?? null;
$simulationLimit = $userId ? $subscriptionHelper->getSimulationLimit($userId) : FREE_SIMULATION_LIMIT;
$hasActiveSubscription = $userId ? $subscriptionHelper->hasActiveSubscription($userId) : false;
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Upload Projections - MLB Pick'em Simulator</title>
    <link rel="apple-touch-icon" sizes="180x180" href="favicon/apple-touch-icon.png">
    <link rel="icon" type="image/png" sizes="32x32" href="favicon/favicon-32x32.png">
    <link rel="icon" type="image/png" sizes="16x16" href="favicon/favicon-16x16.png">
    <link rel="manifest" href="favicon/site.webmanifest">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="css/style.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.7.2/font/bootstrap-icons.css">
    <style>
        #simulation-status {
            display: none;
        }
        .spinner-border {
            width: 1.5rem;
            height: 1.5rem;
            margin-right: 0.5rem;
        }
        #next-steps {
            display: none;
            margin-top: 1.5rem;
        }
        .alert-success .spinner-border {
            display: none !important;
        }
    </style>
</head>
<body>
    <?php include 'header.php'; ?>

    <div class="container mt-4">
        <h1>Upload Projections</h1>
        <h6>Download the template files and upload your projections to the simulator.</h6>
        
        <div class="alert alert-info">
            <p class="mb-0">Subscribed to THE BAT X? You can directly upload <a href="https://rotogrinders.com/grids/standard-projections-the-bat-x-3372510" target="_blank">Standard Projections Files</a> to this simulator.</p>
        </div>
        
        <?php if (!$hasActiveSubscription && $userId): ?>
            <div class="alert alert-warning">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <strong>Upgrade to Premium!</strong> You're currently limited to <?php echo number_format(FREE_SIMULATION_LIMIT); ?> simulations. Get unlimited access with Premium.
                    </div>
                    <a href="subscription.php" class="btn btn-sm btn-primary">Upgrade Now</a>
                </div>
            </div>
        <?php elseif (!$userId): ?>
            <div class="alert alert-info">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <strong>Sign in for more simulations!</strong> Free users get <?php echo number_format(FREE_SIMULATION_LIMIT); ?> simulations. Logged in users get access to subscription plans.
                    </div>
                    <button id="login-prompt" class="btn btn-sm btn-primary" onclick="loginWithGoogle()">Sign In</button>
                </div>
            </div>
        <?php endif; ?>
        
        <div class="alert alert-light">
            <p class="mb-0">Having issues? Contact me via <a href="mailto:aidanhall21@gmail.com">email</a> or Twitter <a href="https://twitter.com/tistonionwings" target="_blank">@tistonionwings</a></p>
        </div>
        
        <div id="simulation-status" class="alert alert-info">
            <div class="d-flex align-items-center">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <span id="status-message"></span>
            </div>
        </div>
        
        <div id="next-steps" class="card">
            <div class="card-body">
                <p class="card-text">What would you like to do next?</p>
                <div class="d-flex gap-2">
                    <a href="props.php" class="btn btn-primary">View Available Props</a>
                </div>
            </div>
        </div>
        
        <form id="upload-form" action="upload.php" method="POST" enctype="multipart/form-data" class="mt-4">
            <div class="mb-3">
                <label for="hitter_projections" class="form-label">Hitter Projections (CSV)</label>
                <div class="input-group">
                    <input type="file" class="form-control" id="hitter_projections" name="hitter_projections" accept=".csv" required>
                    <a href="templates/hitter_template.csv" class="btn btn-outline-secondary" download>Download Template</a>
                </div>
            </div>
            
            <div class="mb-3">
                <label for="pitcher_projections" class="form-label">Pitcher Projections (CSV)</label>
                <div class="input-group">
                    <input type="file" class="form-control" id="pitcher_projections" name="pitcher_projections" accept=".csv" required>
                    <a href="templates/pitcher_template.csv" class="btn btn-outline-secondary" download>Download Template</a>
                </div>
            </div>
            
            <div class="mb-3">
                <label for="num_simulations" class="form-label">Number of Simulations</label>
                <input type="number" class="form-control" id="num_simulations" name="num_simulations" value="500" min="100" max="<?php echo $simulationLimit; ?>" required>
                <div class="form-text">
                    Enter a number between 100 and <?php echo number_format($simulationLimit); ?>. 
                    <?php if (!$hasActiveSubscription && $userId): ?>
                        <a href="subscription.php">Upgrade to Premium</a> for up to <?php echo number_format(PREMIUM_SIMULATION_LIMIT); ?> simulations.
                    <?php elseif (!$userId): ?>
                        Sign in for access to weekly premium plans.
                    <?php endif; ?>
                </div>
            </div>
            
            <button type="submit" class="btn btn-primary">Run Simulations</button>
        </form>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const form = document.getElementById('upload-form');
            const simulationStatus = document.getElementById('simulation-status');
            const statusMessage = document.getElementById('status-message');
            const nextSteps = document.getElementById('next-steps');
            const numSimulationsInput = document.getElementById('num_simulations');
            const numSimulationsHelp = numSimulationsInput.nextElementSibling;
            
            // Function to update simulation limits
            function updateSimulationLimits() {
                // Fetch current limits from server
                fetch('check_subscription.php')
                    .then(response => response.json())
                    .then(data => {
                        const maxSims = data.simulationLimit || <?php echo FREE_SIMULATION_LIMIT; ?>;
                        numSimulationsInput.max = maxSims;
                        let helpText = `Enter a number between 100 and ${maxSims.toLocaleString()}.`;
                        
                        if (!data.hasActiveSubscription && data.isLoggedIn) {
                            helpText += ' <a href="subscription.php">Upgrade to Premium</a> for up to <?php echo number_format(PREMIUM_SIMULATION_LIMIT); ?> simulations.';
                        } else if (!data.isLoggedIn) {
                            helpText += ' Sign in for access to weekly premium plans.';
                        }
                        
                        numSimulationsHelp.innerHTML = helpText;
                    })
                    .catch(error => console.error('Error checking subscription:', error));
            }
            
            // Check initial state
            updateSimulationLimits();
            
            // Listen for login state changes from auth.js
            window.addEventListener('authStateChanged', function(e) {
                updateSimulationLimits();
                
                // Refresh page to update subscription alerts
                if (e.detail.isLoggedIn) {
                    setTimeout(() => {
                        window.location.reload();
                    }, 1000);
                }
            });
            
            form.addEventListener('submit', function(e) {
                e.preventDefault();
                
                // Verify simulation limits before submission
                const numSims = parseInt(numSimulationsInput.value);
                const currentMax = parseInt(numSimulationsInput.max);
                
                if (numSims > currentMax) {
                    alert(`Maximum number of simulations exceeded. Maximum is ${currentMax.toLocaleString()} simulations.`);
                    return;
                }
                
                // Show the simulation status
                simulationStatus.style.display = 'block';
                form.style.display = 'none';
                statusMessage.innerHTML = 'Validating files...';
                
                // Create FormData object
                const formData = new FormData(form);
                
                // Step 1: Validate the files
                fetch('validate_uploads.php', {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Files are valid, update status and run simulation
                        statusMessage.innerHTML = 'Files validated. Running simulations... This may take up to a couple of minutes depending on site traffic.';
                        
                        // Step 2: Run the simulation with validated files
                        const simulationFormData = new FormData();
                        simulationFormData.append('num_simulations', formData.get('num_simulations'));
                        simulationFormData.append('hitter_path', data.hitter_path);
                        simulationFormData.append('pitcher_path', data.pitcher_path);
                        
                        return fetch('run_simulation.php', {
                            method: 'POST',
                            body: simulationFormData,
                            headers: {
                                'X-Requested-With': 'XMLHttpRequest'
                            }
                        });
                    } else {
                        // Files are invalid, show error details
                        simulationStatus.classList.remove('alert-info');
                        simulationStatus.classList.add('alert-danger');
                        
                        let errorMessage = `Error: ${data.error || 'An unknown error occurred'}`;
                        
                        // Format detailed errors if available
                        if (data.details && Array.isArray(data.details)) {
                            errorMessage += '<ul>';
                            data.details.forEach(detail => {
                                if (typeof detail === 'string') {
                                    errorMessage += `<li>${detail}</li>`;
                                } else if (detail.player && detail.blank_columns) {
                                    const cols = Array.isArray(detail.blank_columns) ? detail.blank_columns.join(', ') : detail.blank_columns;
                                    errorMessage += `<li>Player ${detail.player} (row ${detail.row}) has blank values in required columns: ${cols}</li>`;
                                }
                            });
                            errorMessage += '</ul>';
                        }
                        
                        statusMessage.innerHTML = errorMessage;
                        
                        // Hide the spinner
                        document.querySelector('.spinner-border').style.display = 'none';
                        
                        // Add a dismiss button
                        const dismissButton = document.createElement('button');
                        dismissButton.className = 'btn btn-sm btn-outline-light mt-2';
                        dismissButton.textContent = 'Dismiss Error';
                        dismissButton.onclick = function() {
                            window.location.reload();
                        };
                        statusMessage.appendChild(document.createElement('br'));
                        statusMessage.appendChild(dismissButton);
                        
                        throw new Error('Validation failed');
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Show success message and next steps
                        simulationStatus.classList.remove('alert-info');
                        simulationStatus.classList.add('alert-success');
                        statusMessage.innerHTML = data.message;
                        
                        // Hide the spinner
                        document.querySelector('.spinner-border').style.display = 'none';
                        
                        // Show next steps
                        nextSteps.style.display = 'block';
                    } else {
                        // Show error message
                        simulationStatus.classList.remove('alert-info');
                        simulationStatus.classList.add('alert-danger');
                        statusMessage.innerHTML = `Error: ${data.error || 'An unknown error occurred'}`;
                        
                        // Hide the spinner
                        document.querySelector('.spinner-border').style.display = 'none';
                        
                        // Show the error log if available
                        if (data.log) {
                            const errorLog = document.createElement('pre');
                            errorLog.style.marginTop = '10px';
                            errorLog.style.whiteSpace = 'pre-wrap';
                            errorLog.style.fontSize = '12px';
                            errorLog.textContent = data.log;
                            statusMessage.appendChild(errorLog);
                        }
                        
                        // Add a dismiss button
                        const dismissButton = document.createElement('button');
                        dismissButton.className = 'btn btn-sm btn-outline-light mt-2';
                        dismissButton.textContent = 'Dismiss Error';
                        dismissButton.onclick = function() {
                            window.location.reload();
                        };
                        statusMessage.appendChild(document.createElement('br'));
                        statusMessage.appendChild(dismissButton);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    if (error.message !== 'Validation failed') {
                        simulationStatus.classList.remove('alert-info');
                        simulationStatus.classList.add('alert-danger');
                        statusMessage.innerHTML = 'An error occurred while running the simulation. Check the console for details.';
                        
                        // Add a dismiss button if not already added
                        if (!statusMessage.querySelector('button')) {
                            const dismissButton = document.createElement('button');
                            dismissButton.className = 'btn btn-sm btn-outline-light mt-2';
                            dismissButton.textContent = 'Dismiss Error';
                            dismissButton.onclick = function() {
                                window.location.reload();
                            };
                            statusMessage.appendChild(document.createElement('br'));
                            statusMessage.appendChild(dismissButton);
                        }
                    }
                });
            });
        });
    </script>
</body>
</html> 