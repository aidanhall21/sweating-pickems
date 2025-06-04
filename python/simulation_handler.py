import os
import pandas as pd
import logging
import time
import sys
import json
from prop_bitmap import PropBitmap
from redis_helper import RedisHelper
import gzip

# Try different import strategies for MLB_Game_Simulator
try:
    from mlb_slate_simulator import MLB_Game_Simulator
except ImportError:
    try:
        # Try to import from current directory
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from mlb_slate_simulator import MLB_Game_Simulator
    except ImportError:
        # Try to import with python prefix
        from python.mlb_slate_simulator import MLB_Game_Simulator

class SimulationHandler:
    def __init__(self, hitter_file, pitcher_file, num_sims):
        # Convert to absolute paths and validate
        self.hitter_file = os.path.abspath(hitter_file)
        self.pitcher_file = os.path.abspath(pitcher_file)
        
        if not os.path.exists(self.hitter_file):
            raise FileNotFoundError(f"Hitter file not found: {self.hitter_file}")
        if not os.path.exists(self.pitcher_file):
            raise FileNotFoundError(f"Pitcher file not found: {self.pitcher_file}")
            
        self.num_sims = num_sims
        self.redis = RedisHelper.get_instance()
        
        # Set up logging with a less verbose default level
        logging.basicConfig(
            level=logging.WARNING,  # Change default level to WARNING
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Only log important initialization
        self.logger.info('Initialized SimulationHandler')

    def run_simulation(self):
        self.logger.info('Starting simulation')
        start_time = time.time()
        try:
            # Use the uploaded files 
            hitters_path = self.hitter_file
            pitchers_path = self.pitcher_file

            # Run simulation
            sim = MLB_Game_Simulator(self.num_sims, hitters_path, pitchers_path)
            batter_sims, pitcher_sims = sim.run_simulation()

            end_time = time.time()
            self.logger.debug(f'Simulation completed in {end_time - start_time:.2f} seconds')  # Changed to debug
            return batter_sims, pitcher_sims
        except Exception as e:
            self.logger.error(f'Error in run_simulation: {str(e)}')
            raise

    def process_results(self, batter_sims, pitcher_sims):
        self.logger.debug('Processing results')
        start_time = time.time()
        try:
            # Convert lists to dictionaries if needed
            if isinstance(batter_sims, list):
                # Group sims by player
                batter_dict = {}
                for sim in batter_sims:
                    player = sim['player']
                    sim_no = sim['sim_no']
                    if player not in batter_dict:
                        batter_dict[player] = {}
                    batter_dict[player][sim_no] = sim
                batter_sims = batter_dict
                
            if isinstance(pitcher_sims, list):
                # Group sims by player
                pitcher_dict = {}
                for sim in pitcher_sims:
                    player = sim['player']
                    sim_no = sim['sim_no']
                    if player not in pitcher_dict:
                        pitcher_dict[player] = {}
                    pitcher_dict[player][sim_no] = sim
                pitcher_sims = pitcher_dict

            # Initialize bitmap storage with the number of simulations
            first_player_sims = next(iter(batter_sims.values()))
            if isinstance(first_player_sims, dict):
                num_sims = len(first_player_sims)
            else:
                num_sims = len(first_player_sims)
            bitmap_storage = PropBitmap(num_sims)
            
            # For storing preprocessed player stats
            player_stats = {
                'batters': {},
                'pitchers': {}
            }
            
            # Track all players for easy discovery
            all_players = []
            
            # Process batter simulations
            for player_name, sims in batter_sims.items():
                # Create ordered list of sim results
                if isinstance(sims, dict):
                    ordered_sims = [sims[i] for i in range(num_sims)]
                else:
                    ordered_sims = sims
                
                # Clean player name
                player_name = str(player_name).replace(' ', '_').lower()
                all_players.append(player_name)
                
                # Initialize player stats structure
                player_stats['batters'][player_name] = {
                    'stats': {
                        'hits': {},
                        'singles': {},
                        'doubles': {},
                        'home_runs': {},
                        'rbis': {},
                        'runs': {},
                        'total_bases': {},
                        'batter_strikeouts': {},
                        'stolen_bases': {},
                        'hits_runs_rbis': {},
                        'walks': {},
                        'fantasy_points': {},
                        'period_1_hits': {},
                        'period_1_runs': {},
                        'period_1_hits_runs_rbis': {},
                        'period_1_2_3_hits_runs_rbis': {},
                        'first_hit': {'1': 0},
                        'first_rbi': {'1': 0},
                        'first_run': {'1': 0},
                        'first_home_run': {'1': 0}
                    },
                    'total_sims': num_sims
                }
                
                # Track player's bitmap props
                player_bitmap_props = {}
                
                # Hits props
                for hits in range(1, 4):
                    prop_name = f"{player_name}_hits_{hits}_plus"
                    results = [sim['bH'] >= hits for sim in ordered_sims]
                    bitmap_storage.add_prop(prop_name, results)
                    # Store compressed bitmap data for this prop
                    binary_data = bytearray([0] * ((len(results) + 7) // 8))
                    for i, result in enumerate(results):
                        if result:
                            binary_data[i // 8] |= 1 << (i % 8)
                    compressed_data = gzip.compress(bytes(binary_data))
                    player_bitmap_props[f"hits_{hits}_plus"] = [b for b in compressed_data]
                    # Store preprocessed count
                    count = sum(results)
                    player_stats['batters'][player_name]['stats']['hits'][str(hits)] = count
                
                # Singles props
                for singles in range(1, 3):
                    prop_name = f"{player_name}_singles_{singles}_plus"
                    results = [sim['b1B'] >= singles for sim in ordered_sims]
                    bitmap_storage.add_prop(prop_name, results)
                    # Store compressed bitmap data for this prop
                    binary_data = bytearray([0] * ((len(results) + 7) // 8))
                    for i, result in enumerate(results):
                        if result:
                            binary_data[i // 8] |= 1 << (i % 8)
                    compressed_data = gzip.compress(bytes(binary_data))
                    player_bitmap_props[f"singles_{singles}_plus"] = [b for b in compressed_data]
                    # Store preprocessed count
                    count = sum(results)
                    player_stats['batters'][player_name]['stats']['singles'][str(singles)] = count
                
                # Doubles props
                for doubles in range(1, 3):
                    prop_name = f"{player_name}_doubles_{doubles}_plus"
                    results = [sim['b2B'] >= doubles for sim in ordered_sims]
                    bitmap_storage.add_prop(prop_name, results)
                    # Store compressed bitmap data for this prop
                    binary_data = bytearray([0] * ((len(results) + 7) // 8))
                    for i, result in enumerate(results):
                        if result:
                            binary_data[i // 8] |= 1 << (i % 8)
                    compressed_data = gzip.compress(bytes(binary_data))
                    player_bitmap_props[f"doubles_{doubles}_plus"] = [b for b in compressed_data]
                    # Store preprocessed count
                    count = sum(results)
                    player_stats['batters'][player_name]['stats']['doubles'][str(doubles)] = count
                    
                # Home runs props  
                for hrs in range(1, 3):
                    prop_name = f"{player_name}_home_runs_{hrs}_plus"
                    results = [sim['bHR'] >= hrs for sim in ordered_sims]
                    bitmap_storage.add_prop(prop_name, results)
                    # Store compressed bitmap data for this prop
                    binary_data = bytearray([0] * ((len(results) + 7) // 8))
                    for i, result in enumerate(results):
                        if result:
                            binary_data[i // 8] |= 1 << (i % 8)
                    compressed_data = gzip.compress(bytes(binary_data))
                    player_bitmap_props[f"home_runs_{hrs}_plus"] = [b for b in compressed_data]
                    # Store preprocessed count
                    count = sum(results)
                    player_stats['batters'][player_name]['stats']['home_runs'][str(hrs)] = count
                    
                # RBIs props
                for rbis in range(1, 4):
                    prop_name = f"{player_name}_rbis_{rbis}_plus"
                    results = [sim['bRBI'] >= rbis for sim in ordered_sims]
                    bitmap_storage.add_prop(prop_name, results)
                    # Store compressed bitmap data for this prop
                    binary_data = bytearray([0] * ((len(results) + 7) // 8))
                    for i, result in enumerate(results):
                        if result:
                            binary_data[i // 8] |= 1 << (i % 8)
                    compressed_data = gzip.compress(bytes(binary_data))
                    player_bitmap_props[f"rbis_{rbis}_plus"] = [b for b in compressed_data]
                    # Store preprocessed count
                    count = sum(results)
                    player_stats['batters'][player_name]['stats']['rbis'][str(rbis)] = count
                    
                # Runs props
                for runs in range(1, 4):
                    prop_name = f"{player_name}_runs_{runs}_plus"
                    results = [sim['bR'] >= runs for sim in ordered_sims]
                    bitmap_storage.add_prop(prop_name, results)
                    # Store compressed bitmap data for this prop
                    binary_data = bytearray([0] * ((len(results) + 7) // 8))
                    for i, result in enumerate(results):
                        if result:
                            binary_data[i // 8] |= 1 << (i % 8)
                    compressed_data = gzip.compress(bytes(binary_data))
                    player_bitmap_props[f"runs_{runs}_plus"] = [b for b in compressed_data]
                    # Store preprocessed count
                    count = sum(results)
                    player_stats['batters'][player_name]['stats']['runs'][str(runs)] = count
                    
                # Total bases props
                for tb in range(1, 9):
                    prop_name = f"{player_name}_total_bases_{tb}_plus"
                    results = [sim['bTB'] >= tb for sim in ordered_sims]
                    bitmap_storage.add_prop(prop_name, results)
                    # Store compressed bitmap data for this prop
                    binary_data = bytearray([0] * ((len(results) + 7) // 8))
                    for i, result in enumerate(results):
                        if result:
                            binary_data[i // 8] |= 1 << (i % 8)
                    compressed_data = gzip.compress(bytes(binary_data))
                    player_bitmap_props[f"total_bases_{tb}_plus"] = [b for b in compressed_data]
                    # Store preprocessed count
                    count = sum(results)
                    player_stats['batters'][player_name]['stats']['total_bases'][str(tb)] = count
                    
                # Strikeout props
                for ks in range(1, 3):
                    prop_name = f"{player_name}_batter_strikeouts_{ks}_plus"
                    results = [sim['bK'] >= ks for sim in ordered_sims]
                    bitmap_storage.add_prop(prop_name, results)
                    # Store compressed bitmap data for this prop
                    binary_data = bytearray([0] * ((len(results) + 7) // 8))
                    for i, result in enumerate(results):
                        if result:
                            binary_data[i // 8] |= 1 << (i % 8)
                    compressed_data = gzip.compress(bytes(binary_data))
                    player_bitmap_props[f"batter_strikeouts_{ks}_plus"] = [b for b in compressed_data]
                    # Store preprocessed count
                    count = sum(results)
                    player_stats['batters'][player_name]['stats']['batter_strikeouts'][str(ks)] = count
                    
                # Stolen base props
                for sbs in range(1, 3):
                    prop_name = f"{player_name}_stolen_bases_{sbs}_plus"
                    results = [sim['bSB'] >= sbs for sim in ordered_sims]
                    bitmap_storage.add_prop(prop_name, results)
                    # Store compressed bitmap data for this prop
                    binary_data = bytearray([0] * ((len(results) + 7) // 8))
                    for i, result in enumerate(results):
                        if result:
                            binary_data[i // 8] |= 1 << (i % 8)
                    compressed_data = gzip.compress(bytes(binary_data))
                    player_bitmap_props[f"stolen_bases_{sbs}_plus"] = [b for b in compressed_data]
                    # Store preprocessed count
                    count = sum(results)
                    player_stats['batters'][player_name]['stats']['stolen_bases'][str(sbs)] = count
                    
                # Hits + Runs + RBIs props
                for val in range(1, 10):
                    prop_name = f"{player_name}_hits_runs_rbis_{val}_plus"
                    results = [sim['bHRRBI'] >= val for sim in ordered_sims]
                    bitmap_storage.add_prop(prop_name, results)
                    # Store compressed bitmap data for this prop
                    binary_data = bytearray([0] * ((len(results) + 7) // 8))
                    for i, result in enumerate(results):
                        if result:
                            binary_data[i // 8] |= 1 << (i % 8)
                    compressed_data = gzip.compress(bytes(binary_data))
                    player_bitmap_props[f"hits_runs_rbis_{val}_plus"] = [b for b in compressed_data]
                    # Store preprocessed count
                    count = sum(results)
                    player_stats['batters'][player_name]['stats']['hits_runs_rbis'][str(val)] = count
                    
                # Walks props
                for walks in range(1, 3):
                    prop_name = f"{player_name}_walks_{walks}_plus"
                    results = [sim['bBB'] >= walks for sim in ordered_sims]
                    bitmap_storage.add_prop(prop_name, results)
                    # Store compressed bitmap data for this prop
                    binary_data = bytearray([0] * ((len(results) + 7) // 8))
                    for i, result in enumerate(results):
                        if result:
                            binary_data[i // 8] |= 1 << (i % 8)
                    compressed_data = gzip.compress(bytes(binary_data))
                    player_bitmap_props[f"walks_{walks}_plus"] = [b for b in compressed_data]
                    # Store preprocessed count
                    count = sum(results)
                    player_stats['batters'][player_name]['stats']['walks'][str(walks)] = count
                    
                # Fantasy points props
                for pts in range(4, 15):
                    prop_name = f"{player_name}_fantasy_points_{pts}_plus"
                    if pts == 4:
                        # For the first number (4), we want <= 4
                        results = [sim['bUD'] <= 4 for sim in ordered_sims]
                    else:
                        # For all other numbers, we want >= that number
                        results = [sim['bUD'] >= pts for sim in ordered_sims]
                    bitmap_storage.add_prop(prop_name, results)
                    # Store compressed bitmap data for this prop
                    binary_data = bytearray([0] * ((len(results) + 7) // 8))
                    for i, result in enumerate(results):
                        if result:
                            binary_data[i // 8] |= 1 << (i % 8)
                    compressed_data = gzip.compress(bytes(binary_data))
                    player_bitmap_props[f"fantasy_points_{pts}_plus"] = [b for b in compressed_data]
                    # Store preprocessed count
                    count = sum(results)
                    player_stats['batters'][player_name]['stats']['fantasy_points'][str(pts)] = count
                    
                # Period 1 props
                for p1_hits in range(1, 3):
                    prop_name = f"{player_name}_period_1_hits_{p1_hits}_plus"
                    results = [sim['bFirstInnH'] >= p1_hits for sim in ordered_sims]
                    bitmap_storage.add_prop(prop_name, results)
                    # Store compressed bitmap data for this prop
                    binary_data = bytearray([0] * ((len(results) + 7) // 8))
                    for i, result in enumerate(results):
                        if result:
                            binary_data[i // 8] |= 1 << (i % 8)
                    compressed_data = gzip.compress(bytes(binary_data))
                    player_bitmap_props[f"period_1_hits_{p1_hits}_plus"] = [b for b in compressed_data]
                    # Store preprocessed count
                    count = sum(results)
                    player_stats['batters'][player_name]['stats']['period_1_hits'][str(p1_hits)] = count
                
                for p1_runs in range(1, 3):
                    prop_name = f"{player_name}_period_1_runs_{p1_runs}_plus"
                    results = [sim['bFirstInnR'] >= p1_runs for sim in ordered_sims]
                    bitmap_storage.add_prop(prop_name, results)
                    # Store compressed bitmap data for this prop
                    binary_data = bytearray([0] * ((len(results) + 7) // 8))
                    for i, result in enumerate(results):
                        if result:
                            binary_data[i // 8] |= 1 << (i % 8)
                    compressed_data = gzip.compress(bytes(binary_data))
                    player_bitmap_props[f"period_1_runs_{p1_runs}_plus"] = [b for b in compressed_data]
                    # Store preprocessed count
                    count = sum(results)
                    player_stats['batters'][player_name]['stats']['period_1_runs'][str(p1_runs)] = count
                
                for p1_hits_runs_rbis in range(1, 4):
                    prop_name = f"{player_name}_period_1_hits_runs_rbis_{p1_hits_runs_rbis}_plus"
                    results = [sim['bFirstInnHRBI'] >= p1_hits_runs_rbis for sim in ordered_sims]
                    bitmap_storage.add_prop(prop_name, results)
                    # Store compressed bitmap data for this prop
                    binary_data = bytearray([0] * ((len(results) + 7) // 8))
                    for i, result in enumerate(results):
                        if result:
                            binary_data[i // 8] |= 1 << (i % 8)
                    compressed_data = gzip.compress(bytes(binary_data))
                    player_bitmap_props[f"period_1_hits_runs_rbis_{p1_hits_runs_rbis}_plus"] = [b for b in compressed_data]
                    # Store preprocessed count
                    count = sum(results)
                    player_stats['batters'][player_name]['stats']['period_1_hits_runs_rbis'][str(p1_hits_runs_rbis)] = count
                
                # Period 1-3 props
                for p1_3_hits_runs_rbis in range(1, 4):
                    prop_name = f"{player_name}_period_1_2_3_hits_runs_rbis_{p1_3_hits_runs_rbis}_plus"
                    results = [sim['bFirst3InnHRBI'] >= p1_3_hits_runs_rbis for sim in ordered_sims]
                    bitmap_storage.add_prop(prop_name, results)
                    # Store compressed bitmap data for this prop
                    binary_data = bytearray([0] * ((len(results) + 7) // 8))
                    for i, result in enumerate(results):
                        if result:
                            binary_data[i // 8] |= 1 << (i % 8)
                    compressed_data = gzip.compress(bytes(binary_data))
                    player_bitmap_props[f"period_1_2_3_hits_runs_rbis_{p1_3_hits_runs_rbis}_plus"] = [b for b in compressed_data]
                    # Store preprocessed count
                    count = sum(results)
                    player_stats['batters'][player_name]['stats']['period_1_2_3_hits_runs_rbis'][str(p1_3_hits_runs_rbis)] = count
                
                # First occurrence props
                prop_name = f"{player_name}_first_hit"
                results = [sim['bFirstHit'] == 1 for sim in ordered_sims]
                bitmap_storage.add_prop(prop_name, results)
                # Store compressed bitmap data for this prop
                binary_data = bytearray([0] * ((len(results) + 7) // 8))
                for i, result in enumerate(results):
                    if result:
                        binary_data[i // 8] |= 1 << (i % 8)
                compressed_data = gzip.compress(bytes(binary_data))
                player_bitmap_props["first_hit"] = [b for b in compressed_data]
                # Store preprocessed count
                count = sum(results)
                player_stats['batters'][player_name]['stats']['first_hit']['1'] = count
                
                prop_name = f"{player_name}_first_rbi"
                results = [sim['bFirstRBI'] == 1 for sim in ordered_sims]
                bitmap_storage.add_prop(prop_name, results)
                # Store compressed bitmap data for this prop
                binary_data = bytearray([0] * ((len(results) + 7) // 8))
                for i, result in enumerate(results):
                    if result:
                        binary_data[i // 8] |= 1 << (i % 8)
                compressed_data = gzip.compress(bytes(binary_data))
                player_bitmap_props["first_rbi"] = [b for b in compressed_data]
                # Store preprocessed count
                count = sum(results)
                player_stats['batters'][player_name]['stats']['first_rbi']['1'] = count
                
                prop_name = f"{player_name}_first_run"
                results = [sim['bFirstRun'] == 1 for sim in ordered_sims]
                bitmap_storage.add_prop(prop_name, results)
                # Store compressed bitmap data for this prop
                binary_data = bytearray([0] * ((len(results) + 7) // 8))
                for i, result in enumerate(results):
                    if result:
                        binary_data[i // 8] |= 1 << (i % 8)
                compressed_data = gzip.compress(bytes(binary_data))
                player_bitmap_props["first_run"] = [b for b in compressed_data]
                # Store preprocessed count
                count = sum(results)
                player_stats['batters'][player_name]['stats']['first_run']['1'] = count
                
                prop_name = f"{player_name}_first_home_run"
                results = [sim['bFirstHR'] == 1 for sim in ordered_sims]
                bitmap_storage.add_prop(prop_name, results)
                # Store compressed bitmap data for this prop
                binary_data = bytearray([0] * ((len(results) + 7) // 8))
                for i, result in enumerate(results):
                    if result:
                        binary_data[i // 8] |= 1 << (i % 8)
                compressed_data = gzip.compress(bytes(binary_data))
                player_bitmap_props["first_home_run"] = [b for b in compressed_data]
                # Store preprocessed count
                count = sum(results)
                player_stats['batters'][player_name]['stats']['first_home_run']['1'] = count
                
                # Store player's bitmap props
                try:
                    # Break down large data into smaller chunks
                    chunk_size = 1000  # Number of props per chunk
                    # Convert dictionary to list of items and chunk it
                    items = list(player_bitmap_props.items())
                    props_chunks = [dict(items[i:i + chunk_size]) for i in range(0, len(items), chunk_size)]
                    
                    for i, chunk in enumerate(props_chunks):
                        chunk_key = f'pickem_player_bitmap_{player_name}_chunk_{i}'
                        self.redis.set(chunk_key, json.dumps(chunk))
                    
                    # Store metadata about chunks
                    chunk_metadata = {
                        'num_chunks': len(props_chunks),
                        'total_props': len(player_bitmap_props)
                    }
                    self.redis.set(f'pickem_player_bitmap_{player_name}_metadata', json.dumps(chunk_metadata))
                except Exception as e:
                    self.logger.error(f'Error storing player bitmap data for {player_name}: {str(e)}')
                    raise
            
            # Process pitcher simulations
            for player_name, sims in pitcher_sims.items():
                # Create ordered list of sim results
                if isinstance(sims, dict):
                    ordered_sims = [sims[i] for i in range(num_sims)]
                else:
                    ordered_sims = sims
                    
                # Clean player name
                player_name = str(player_name).replace(' ', '_').lower()
                all_players.append(player_name)
                
                # Initialize player stats structure
                player_stats['pitchers'][player_name] = {
                    'stats': {
                        'strikeouts': {},
                        'walks_allowed': {},
                        'runs_allowed': {},
                        'hits_allowed': {},
                        'pitch_outs': {},
                        'fantasy_points': {},
                        'period_1_strikeouts': {},
                        'period_1_total_runs_allowed': {},
                        'period_1_hits_allowed': {},
                        'period_1_pitch_count': {},
                        'period_1_batters_faced': {},
                        'period_1_2_3_total_runs_allowed': {},
                        'period_first_strikeout': {'1': 0},
                        'period_first_earned_run': {'1': 0}
                    },
                    'total_sims': num_sims
                }
                
                # Track player's bitmap props
                player_bitmap_props = {}
                
                # Strikeouts props
                for ks in range(2, 11):
                    prop_name = f"{player_name}_strikeouts_{ks}_plus"
                    if ks == 2:
                        results = [sim['pK'] <= 2 for sim in ordered_sims]
                    else:
                        results = [sim['pK'] >= ks for sim in ordered_sims]
                    bitmap_storage.add_prop(prop_name, results)
                    # Store compressed bitmap data for this prop
                    binary_data = bytearray([0] * ((len(results) + 7) // 8))
                    for i, result in enumerate(results):
                        if result:
                            binary_data[i // 8] |= 1 << (i % 8)
                    compressed_data = gzip.compress(bytes(binary_data))
                    player_bitmap_props[f"strikeouts_{ks}_plus"] = [b for b in compressed_data]
                    # Store preprocessed count
                    count = sum(results)
                    player_stats['pitchers'][player_name]['stats']['strikeouts'][str(ks)] = count
                    
                # Walks allowed props
                for walks in range(1, 6):
                    prop_name = f"{player_name}_walks_allowed_{walks}_plus"
                    results = [sim['pBB'] >= walks for sim in ordered_sims]
                    bitmap_storage.add_prop(prop_name, results)
                    # Store compressed bitmap data for this prop
                    binary_data = bytearray([0] * ((len(results) + 7) // 8))
                    for i, result in enumerate(results):
                        if result:
                            binary_data[i // 8] |= 1 << (i % 8)
                    compressed_data = gzip.compress(bytes(binary_data))
                    player_bitmap_props[f"walks_allowed_{walks}_plus"] = [b for b in compressed_data]
                    # Store preprocessed count
                    count = sum(results)
                    player_stats['pitchers'][player_name]['stats']['walks_allowed'][str(walks)] = count
                    
                # Runs allowed props
                for runs in range(1, 8):
                    prop_name = f"{player_name}_runs_allowed_{runs}_plus"
                    results = [sim['pR'] >= runs for sim in ordered_sims]
                    bitmap_storage.add_prop(prop_name, results)
                    # Store compressed bitmap data for this prop
                    binary_data = bytearray([0] * ((len(results) + 7) // 8))
                    for i, result in enumerate(results):
                        if result:
                            binary_data[i // 8] |= 1 << (i % 8)
                    compressed_data = gzip.compress(bytes(binary_data))
                    player_bitmap_props[f"runs_allowed_{runs}_plus"] = [b for b in compressed_data]
                    # Store preprocessed count
                    count = sum(results)
                    player_stats['pitchers'][player_name]['stats']['runs_allowed'][str(runs)] = count
                    
                # Hits allowed props
                for hits in range(3, 10):
                    prop_name = f"{player_name}_hits_allowed_{hits}_plus"
                    if hits == 3:
                        results = [sim['pH'] <= 3 for sim in ordered_sims]
                    else:
                        results = [sim['pH'] >= hits for sim in ordered_sims]
                    bitmap_storage.add_prop(prop_name, results)
                    # Store compressed bitmap data for this prop
                    binary_data = bytearray([0] * ((len(results) + 7) // 8))
                    for i, result in enumerate(results):
                        if result:
                            binary_data[i // 8] |= 1 << (i % 8)
                    compressed_data = gzip.compress(bytes(binary_data))
                    player_bitmap_props[f"hits_allowed_{hits}_plus"] = [b for b in compressed_data]
                    # Store preprocessed count
                    count = sum(results)
                    player_stats['pitchers'][player_name]['stats']['hits_allowed'][str(hits)] = count
                    
                # Outs recorded props
                for outs in range(12, 22):
                    prop_name = f"{player_name}_pitch_outs_{outs}_plus"
                    if outs == 12:
                        # For the first number (9), we want <= 9
                        results = [sim['pOuts'] <= 12 for sim in ordered_sims]
                    else:
                        # For all other numbers, we want >= that number
                        results = [sim['pOuts'] >= outs for sim in ordered_sims]
                    bitmap_storage.add_prop(prop_name, results)
                    # Store compressed bitmap data for this prop
                    binary_data = bytearray([0] * ((len(results) + 7) // 8))
                    for i, result in enumerate(results):
                        if result:
                            binary_data[i // 8] |= 1 << (i % 8)
                    compressed_data = gzip.compress(bytes(binary_data))
                    player_bitmap_props[f"pitch_outs_{outs}_plus"] = [b for b in compressed_data]
                    # Store preprocessed count
                    count = sum(results)
                    player_stats['pitchers'][player_name]['stats']['pitch_outs'][str(outs)] = count
                    
                # Fantasy points props
                for pts in range(18, 41):
                    prop_name = f"{player_name}_fantasy_points_{pts}_plus"
                    if pts == 18:
                        # For the first number (15), we want <= 15
                        results = [sim['pUD'] <= 18 for sim in ordered_sims]
                    else:
                        # For all other numbers, we want >= that number
                        results = [sim['pUD'] >= pts for sim in ordered_sims]
                    bitmap_storage.add_prop(prop_name, results)
                    # Store compressed bitmap data for this prop
                    binary_data = bytearray([0] * ((len(results) + 7) // 8))
                    for i, result in enumerate(results):
                        if result:
                            binary_data[i // 8] |= 1 << (i % 8)
                    compressed_data = gzip.compress(bytes(binary_data))
                    player_bitmap_props[f"fantasy_points_{pts}_plus"] = [b for b in compressed_data]
                    # Store preprocessed count
                    count = sum(results)
                    player_stats['pitchers'][player_name]['stats']['fantasy_points'][str(pts)] = count
                    
                # Period 1 props
                for ks in range(1, 4):
                    prop_name = f"{player_name}_period_1_strikeouts_{ks}_plus"
                    results = [sim['pFirstInnK'] >= ks for sim in ordered_sims]
                    bitmap_storage.add_prop(prop_name, results)
                    # Store compressed bitmap data for this prop
                    binary_data = bytearray([0] * ((len(results) + 7) // 8))
                    for i, result in enumerate(results):
                        if result:
                            binary_data[i // 8] |= 1 << (i % 8)
                    compressed_data = gzip.compress(bytes(binary_data))
                    player_bitmap_props[f"period_1_strikeouts_{ks}_plus"] = [b for b in compressed_data]
                    # Store preprocessed count
                    count = sum(results)
                    player_stats['pitchers'][player_name]['stats']['period_1_strikeouts'][str(ks)] = count
                    
                for runs in range(1, 3):
                    prop_name = f"{player_name}_period_1_total_runs_allowed_{runs}_plus"
                    results = [sim['pFirstInnR'] >= runs for sim in ordered_sims]
                    bitmap_storage.add_prop(prop_name, results)
                    # Store compressed bitmap data for this prop
                    binary_data = bytearray([0] * ((len(results) + 7) // 8))
                    for i, result in enumerate(results):
                        if result:
                            binary_data[i // 8] |= 1 << (i % 8)
                    compressed_data = gzip.compress(bytes(binary_data))
                    player_bitmap_props[f"period_1_total_runs_allowed_{runs}_plus"] = [b for b in compressed_data]
                    # Store preprocessed count
                    count = sum(results)
                    player_stats['pitchers'][player_name]['stats']['period_1_total_runs_allowed'][str(runs)] = count
                    
                for hits in range(1, 3):
                    prop_name = f"{player_name}_period_1_hits_allowed_{hits}_plus"
                    results = [sim['pFirstInnH'] >= hits for sim in ordered_sims]
                    bitmap_storage.add_prop(prop_name, results)
                    # Store compressed bitmap data for this prop
                    binary_data = bytearray([0] * ((len(results) + 7) // 8))
                    for i, result in enumerate(results):
                        if result:
                            binary_data[i // 8] |= 1 << (i % 8)
                    compressed_data = gzip.compress(bytes(binary_data))
                    player_bitmap_props[f"period_1_hits_allowed_{hits}_plus"] = [b for b in compressed_data]
                    # Store preprocessed count
                    count = sum(results)
                    player_stats['pitchers'][player_name]['stats']['period_1_hits_allowed'][str(hits)] = count
                    
                # Period 1 pitch count props
                for pc in range(20, 21):
                    prop_name = f"{player_name}_period_1_pitch_count_{pc}_plus"
                    results = [sim['pFirstInnPC'] >= pc for sim in ordered_sims]
                    bitmap_storage.add_prop(prop_name, results)
                    # Store compressed bitmap data for this prop
                    binary_data = bytearray([0] * ((len(results) + 7) // 8))
                    for i, result in enumerate(results):
                        if result:
                            binary_data[i // 8] |= 1 << (i % 8)
                    compressed_data = gzip.compress(bytes(binary_data))
                    player_bitmap_props[f"period_1_pitch_count_{pc}_plus"] = [b for b in compressed_data]
                    # Store preprocessed count
                    count = sum(results)
                    player_stats['pitchers'][player_name]['stats']['period_1_pitch_count'][str(pc)] = count
                    
                # Period 1 batters faced props
                for bf in range(4, 5):
                    prop_name = f"{player_name}_period_1_batters_faced_{bf}_plus"
                    results = [sim['pFirstInnBF'] >= bf for sim in ordered_sims]
                    bitmap_storage.add_prop(prop_name, results)
                    # Store compressed bitmap data for this prop
                    binary_data = bytearray([0] * ((len(results) + 7) // 8))
                    for i, result in enumerate(results):
                        if result:
                            binary_data[i // 8] |= 1 << (i % 8)
                    compressed_data = gzip.compress(bytes(binary_data))
                    player_bitmap_props[f"period_1_batters_faced_{bf}_plus"] = [b for b in compressed_data]
                    # Store preprocessed count
                    count = sum(results)
                    player_stats['pitchers'][player_name]['stats']['period_1_batters_faced'][str(bf)] = count
                    
                for runs in range(1, 5):
                    prop_name = f"{player_name}_period_1_2_3_total_runs_allowed_{runs}_plus"
                    results = [sim['pFirst3InnR'] >= runs for sim in ordered_sims]
                    bitmap_storage.add_prop(prop_name, results)
                    # Store compressed bitmap data for this prop
                    binary_data = bytearray([0] * ((len(results) + 7) // 8))
                    for i, result in enumerate(results):
                        if result:
                            binary_data[i // 8] |= 1 << (i % 8)
                    compressed_data = gzip.compress(bytes(binary_data))
                    player_bitmap_props[f"period_1_2_3_total_runs_allowed_{runs}_plus"] = [b for b in compressed_data]
                    # Store preprocessed count
                    count = sum(results)
                    player_stats['pitchers'][player_name]['stats']['period_1_2_3_total_runs_allowed'][str(runs)] = count
                    
                # First occurrence props
                prop_name = f"{player_name}_period_first_strikeout"
                results = [sim['pFirstK'] == 1 for sim in ordered_sims]
                bitmap_storage.add_prop(prop_name, results)
                # Store compressed bitmap data for this prop
                binary_data = bytearray([0] * ((len(results) + 7) // 8))
                for i, result in enumerate(results):
                    if result:
                        binary_data[i // 8] |= 1 << (i % 8)
                compressed_data = gzip.compress(bytes(binary_data))
                player_bitmap_props["period_first_strikeout"] = [b for b in compressed_data]
                # Store preprocessed count
                count = sum(results)
                player_stats['pitchers'][player_name]['stats']['period_first_strikeout']['1'] = count
                
                prop_name = f"{player_name}_period_first_earned_run"
                results = [sim['pFirstRunAllowed'] == 1 for sim in ordered_sims]
                bitmap_storage.add_prop(prop_name, results)
                # Store compressed bitmap data for this prop
                binary_data = bytearray([0] * ((len(results) + 7) // 8))
                for i, result in enumerate(results):
                    if result:
                        binary_data[i // 8] |= 1 << (i % 8)
                compressed_data = gzip.compress(bytes(binary_data))
                player_bitmap_props["period_first_earned_run"] = [b for b in compressed_data]
                # Store preprocessed count
                count = sum(results)
                player_stats['pitchers'][player_name]['stats']['period_first_earned_run']['1'] = count
                
                # Store player's bitmap props
                try:
                    # Break down large data into smaller chunks
                    chunk_size = 1000  # Number of props per chunk
                    # Convert dictionary to list of items and chunk it
                    items = list(player_bitmap_props.items())
                    props_chunks = [dict(items[i:i + chunk_size]) for i in range(0, len(items), chunk_size)]
                    
                    for i, chunk in enumerate(props_chunks):
                        chunk_key = f'pickem_player_bitmap_{player_name}_chunk_{i}'
                        self.redis.set(chunk_key, json.dumps(chunk))
                    
                    # Store metadata about chunks
                    chunk_metadata = {
                        'num_chunks': len(props_chunks),
                        'total_props': len(player_bitmap_props)
                    }
                    self.redis.set(f'pickem_player_bitmap_{player_name}_metadata', json.dumps(chunk_metadata))
                except Exception as e:
                    self.logger.error(f'Error storing player bitmap data for {player_name}: {str(e)}')
                    raise
            
            # Store simulation data in Redis
            try:
                # Store metadata
                metadata = {
                    'num_sims': bitmap_storage.num_sims,
                    'timestamp': int(time.time())
                }
                self.redis.set('pickem_simulation_metadata', json.dumps(metadata))
                
                # Store the list of all players
                self.redis.set('pickem_players_list', json.dumps(list(set(all_players))))
                
                # Store all player stats in one key
                self.redis.set('pickem_all_player_stats', json.dumps(player_stats))
                
                self.logger.info('Successfully stored simulation data in Redis')
            except Exception as e:
                self.logger.error(f'Failed to store simulation data in Redis: {str(e)}')
                raise

            end_time = time.time()
            self.logger.debug(f'Results processed in {end_time - start_time:.2f} seconds')
            
            return bitmap_storage

        except Exception as e:
            self.logger.error(f'Error in process_results: {str(e)}')
            raise

    def load_props(self):
        """Load props from Redis.
        
        Returns:
            PropBitmap instance containing the loaded props
        """
        try:
            data = self.redis.get('simulation_data')
            if data is None:
                raise Exception("No simulation data found in Redis")
                
            # Create PropBitmap from data
            bitmap_storage = PropBitmap.from_json(data)
            
            self.logger.info('Props loaded from Redis')
            
            return bitmap_storage
            
        except Exception as e:
            self.logger.error(f'Error loading props: {str(e)}')
            raise

