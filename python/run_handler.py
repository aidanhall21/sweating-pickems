import sys
import os
import logging
import csv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('python_simulation.log')
    ]
)
logger = logging.getLogger(__name__)

# Get the directory of this script
script_dir = os.path.dirname(os.path.abspath(__file__))
# Add the parent directory to path to find modules
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)
# Add python directory to path
python_dir = os.path.join(parent_dir, 'python')
sys.path.insert(0, python_dir)

try:
    from python.simulation_handler import SimulationHandler
except ImportError:
    # Try alternative import paths
    try:
        from simulation_handler import SimulationHandler
    except ImportError:
        logger.error(f"Import error: {traceback.format_exc()}")
        logger.error(f"sys.path: {sys.path}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        # Get absolute paths for input files
        hitter_file = os.path.abspath(sys.argv[1])
        pitcher_file = os.path.abspath(sys.argv[2])
        num_sims = int(sys.argv[3])
        
        # Validate file paths
        if not os.path.exists(hitter_file):
            raise FileNotFoundError(f"Hitter file not found: {hitter_file}")
        if not os.path.exists(pitcher_file):
            raise FileNotFoundError(f"Pitcher file not found: {pitcher_file}")
        
        logger.info(f"Starting simulation with: {hitter_file}, {pitcher_file}, {num_sims}")
        
        handler = SimulationHandler(hitter_file, pitcher_file, num_sims)
        batter_sims, pitcher_sims = handler.run_simulation()
        
        # # Log first few rows of batter simulations
        # logger.info("First few rows of batter simulations:")
        # for i, row in enumerate(batter_sims[:3]):
        #     logger.info(f"Row {i+1}: {row}")
            
        # # Log first few rows of pitcher simulations
        # logger.info("First few rows of pitcher simulations:")
        # for i, row in enumerate(pitcher_sims[:3]):
        #     logger.info(f"Row {i+1}: {row}")
        
        # Save batter simulations to CSV
        # with open('data/batter_simulations.csv', 'w', newline='') as f:
        #     writer = csv.writer(f)
        #     # Write header
        #     writer.writerow(batter_sims[0].keys())
        #     # Write data
        #     for row in batter_sims:
        #         writer.writerow(row.values())
                
        # # Save pitcher simulations to CSV
        # with open('data/pitcher_simulations.csv', 'w', newline='') as f:
        #     writer = csv.writer(f)
        #     # Write header
        #     writer.writerow(pitcher_sims[0].keys())
        #     # Write data
        #     for row in pitcher_sims:
        #         writer.writerow(row.values())
        
        results = handler.process_results(batter_sims, pitcher_sims)
        
        print('{"success": true, "message": "Simulation completed successfully"}')
    except Exception as e:
        import traceback
        logger.error(f"Error: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        print(f'{{"success": false, "error": "{str(e)}"}}')
        sys.exit(1)