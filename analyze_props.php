<?php
require_once 'config.php';
require_once 'redis_helper.php';
session_start();

// Try to get simulation results from Redis first
$redis = RedisHelper::getInstance();
$simulation_data = $redis->get('pickem_sim_metadata');

if (!$simulation_data && !isset($_SESSION['simulation_results'])) {
    header('Location: upload.php');
    exit;
}

// Get selected props from URL parameter
$selectedProps = json_decode($_GET['props'] ?? '[]', true);
if (empty($selectedProps)) {
    header('Location: props.php');
    exit;
}

// Calculate win probabilities and EV
$analysisResults = [];
foreach ($selectedProps as $propId) {
    $command = sprintf('python3 python/analyze_prop.py --prop %s --redis_key pickem_sim_', escapeshellarg($propId));
    $output = [];
    exec($command . ' 2>&1', $output, $return_var);
    
    if ($return_var === 0) {
        $propData = json_decode(implode("\n", $output), true);
        if ($propData) {
            $analysisResults[] = $propData;
        }
    }
}

// Return results as JSON
header('Content-Type: application/json');
echo json_encode([
    'success' => true,
    'results' => $analysisResults
]);

// Helper functions
function calculateHitProbability($results, $line) {
    $hits = array_column($results, 'hits');
    $total = count($hits);
    $wins = count(array_filter($hits, function($h) use ($line) { return $h >= $line; }));
    return $wins / $total;
}

function calculateStrikeoutProbability($results, $line) {
    $ks = array_column($results, 'strikeouts');
    $total = count($ks);
    $wins = count(array_filter($ks, function($k) use ($line) { return $k >= $line; }));
    return $wins / $total;
}

function convertAmericanToDecimal($americanOdds) {
    if ($americanOdds > 0) {
        return ($americanOdds / 100) + 1;
    } else {
        return (100 / abs($americanOdds)) + 1;
    }
}
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prop Analysis - MLB Pick'em Simulator</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="css/style.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="index.php">MLB Pick'em Simulator</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav">
                    <li class="nav-item">
                        <a class="nav-link" href="upload.php">Upload Projections</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="props.php">View Props</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link active" href="simulations.php">Simulation Results</a>
                    </li>
                </ul>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        <h1>Prop Analysis Results</h1>
        <p>Analysis of selected props based on simulation results.</p>
        
        <div class="row mt-4">
            <div class="col-md-12">
                <div class="card">
                    <div class="card-body">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Player</th>
                                    <th>Prop Type</th>
                                    <th>Line</th>
                                    <th>Odds</th>
                                    <th>Win Probability</th>
                                    <th>Expected Value</th>
                                </tr>
                            </thead>
                            <tbody>
                                <?php foreach ($analysisResults as $result): ?>
                                    <tr class="<?php echo $result['ev'] > 0 ? 'table-success' : ''; ?>">
                                        <td><?php echo htmlspecialchars($result['player']); ?></td>
                                        <td><?php echo htmlspecialchars($result['type']); ?></td>
                                        <td><?php echo htmlspecialchars($result['line']); ?></td>
                                        <td><?php echo htmlspecialchars($result['odds']); ?></td>
                                        <td><?php echo number_format($result['win_probability'] * 100, 1); ?>%</td>
                                        <td><?php echo number_format($result['ev'] * 100, 1); ?>%</td>
                                    </tr>
                                <?php endforeach; ?>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html> 