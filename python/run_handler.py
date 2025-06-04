import sys
import os
import logging
import csv
import traceback

# Get the directory of this script
script_dir = os.path.dirname(os.path.abspath(__file__))
# Add the parent directory to path to find modules
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)
# Add python directory to path
python_dir = os.path.join(parent_dir, 'python')
sys.path.insert(0, python_dir)

# Set up logging
log_file = os.path.join(parent_dir, 'python_simulation.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger(__name__)

logger.info(f"Script directory: {script_dir}")
logger.info(f"Parent directory: {parent_dir}")
logger.info(f"Python directory: {python_dir}")
logger.info(f"Log file: {log_file}")
logger.info(f"sys.path: {sys.path}")

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
        
        logger.info(f"Input files - Hitter: {hitter_file}, Pitcher: {pitcher_file}")
        logger.info(f"Number of simulations: {num_sims}")
        
        # Validate file paths
        if not os.path.exists(hitter_file):
            raise FileNotFoundError(f"Hitter file not found: {hitter_file}")
        if not os.path.exists(pitcher_file):
            raise FileNotFoundError(f"Pitcher file not found: {pitcher_file}")
        
        logger.info(f"Starting simulation with: {hitter_file}, {pitcher_file}, {num_sims}")
        
        handler = SimulationHandler(hitter_file, pitcher_file, num_sims)
        logger.info("Created SimulationHandler instance")
        
        batter_sims, pitcher_sims = handler.run_simulation()
        logger.info("Simulation completed successfully")
        
        results = handler.process_results(batter_sims, pitcher_sims)
        logger.info("Results processed successfully")
        
        print('{"success": true, "message": "Simulation completed successfully"}')
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        print(f'{{"success": false, "error": "{str(e)}"}}')
        sys.exit(1)