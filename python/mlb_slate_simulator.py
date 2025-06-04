import collections
import csv
import itertools
import multiprocessing as mp
import numpy as np
import pandas as pd
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MLB_Game_Simulator:
    def __init__(self, num_sims, hitter_file_path, pitcher_file_path):
        self.num_sims = int(num_sims)
        self.hitter_file_path = hitter_file_path
        self.pitcher_file_path = pitcher_file_path
        self.dh = "2"
        self.id_counter = 1
        self.hitters_dict = {}
        self.pitchers_dict = {}
        self.teams_dict = collections.defaultdict(list)
        self.pitcher_totals = collections.defaultdict(dict)
        self.hitter_totals_vs_sp = collections.defaultdict(dict)
        self.games = []
        # Pre-allocate numpy arrays for better memory efficiency
        self.random_cache_size = 10000
        self.random_cache = np.random.random(self.random_cache_size)
        self.random_cache_index = 0
        
        self.replacement_hitter = {
            "PA": 10,
            "1B": 1.27,
            "2B": 0.36,
            "3B": 0.02,
            "HR": 0.21,
            "SB": 0.37,
            "CS": 0.087,
            "K": 2.99,
            "BB": 1.16,
            "HBP": 0.14,
            "OUT": 6.84
        }

        self.load_projections()
        
    def get_random(self):
        """Get a random number from pre-allocated cache"""
        if self.random_cache_index >= self.random_cache_size:
            self.random_cache = np.random.random(self.random_cache_size)
            self.random_cache_index = 0
        val = self.random_cache[self.random_cache_index]
        self.random_cache_index += 1
        return val

        self.load_projections()

    def lower_first(self, iterator):
        iterator = iter(iterator)
        # Skip comment lines
        for line in iterator:
            if not line.strip().startswith("#"):
                # Lowercase the header row and yield it
                yield line.lower()
                break
        # Yield the rest of the file unchanged
        for line in iterator:
            yield line

    def load_pitcher_totals(self, path):
        with open(path, encoding="utf-8-sig") as file:
            reader = csv.DictReader(self.lower_first(file))
            for row in reader:
                if "2h" in row and row["2h"] == self.dh:
                    continue
                opener = False
                if "mpc" in row and row["mpc"] == "IP CAP":
                    opener = True
                opponent = row.get("opp_tm") or row.get("opp")
                pitcher_totals = {
                    "H": float(row['h']),
                    "HR": float(row["hr"]),
                    "SB": float(row.get("sb", 0.5)),
                    "CS": float(row.get("cs", 0.15)),
                    "K": float(row["k"]),
                    "BB": float(row["bb"]),
                    "HBP": float(row["hbp"]) if row["hbp"] else 0.0,
                    "OUT": float(row['outs']) if row['outs'] else float(row['ip']) * 3,
                }
                if opponent in self.pitcher_totals:
                    if opener:
                        opener_value = row["opener"]
                        if "Yes" in opener_value:
                            pass
                        else:
                            self.pitcher_totals[opponent] = pitcher_totals
                    else:
                        self.pitcher_totals[opponent] = pitcher_totals
                else:
                    self.pitcher_totals[opponent] = pitcher_totals

    def load_hitter_totals(self, path):
        team_order = {}  # Dictionary to track order of teams
        with open(path, encoding="utf-8-sig") as file:
            reader = csv.DictReader(self.lower_first(file))
            for row in reader:
                if "2h" in row and row["2h"] == self.dh:
                    continue
                if not row["hbp"] or not row["hbp"].strip():
                    row["hbp"] = "0"
                if not row["cs"] or not row["cs"].strip():
                    row["cs"] = "0.05"
                team = row.get('team') or row.get('tm')
                if not row["lp"] or not row["lp"].strip():
                    # Increment team order counter
                    team_order[team] = team_order.get(team, 0) + 1
                    row["lp"] = str(team_order[team])
                if ("ipl" in row and row["ipl"] == "false") or float(row["lp"]) > 9:
                    player_data = {
                        "PA": float(row["pa"]),
                        "1B": float(row["1b"]),
                        "2B": float(row["2b"]),
                        "3B": float(row["3b"]),
                        "HR": float(row["hr"]),
                        "SB": float(row["sb"]),
                        "CS": float(row["cs"]),
                        "K": float(row["k"]),
                        "BB": float(row["bb"]),
                        "HBP": float(row["hbp"]),
                        "OUT": 1 - float(row["_obp"])
                    }
                    for key, val in player_data.items():
                        if key in self.replacement_hitter:
                            self.replacement_hitter[key] += val
                        else:
                            self.replacement_hitter[key] = val
                else:
                    if "pavssp" in row:
                        pavssp = float(row["pavssp%"].replace("%", '')) / 100
                    else:
                        pavssp = .053 + -.007 * float(row["lp"]) + .038 * float(self.pitcher_totals[team]["OUT"])
                    if "_obp" in row:
                        outs = (1 - float(row["_obp"])) * float(row["pa"])
                    else:
                        outs = float(row["pa"]) - float(row["bb"]) - float(row["hbp"]) - float(row["1b"]) - float(row["2b"]) - float(row["3b"]) - float(row["hr"])
                    h = (float(row["1b"]) + float(row["2b"]) + float(row["3b"]) + float(row["hr"])) * pavssp
                    hr = float(row["hr"]) * pavssp
                    sb = float(row["sb"]) * pavssp
                    cs = float(row["cs"]) * pavssp
                    k = float(row["k"]) * pavssp
                    bb = float(row["bb"]) * pavssp
                    hbp = float(row["hbp"]) * pavssp
                    out = outs * pavssp
                    player_data = {
                        "HR": hr,
                        "H": h,
                        "SB": sb,
                        "CS": cs,
                        "K": k,
                        "BB": bb,
                        "HBP": hbp,
                        "OUT": out
                    }

                    if team in self.hitter_totals_vs_sp:
                        for key, val in player_data.items():
                            if key in self.hitter_totals_vs_sp[team]:
                                self.hitter_totals_vs_sp[team][key] += val
                            else:
                                self.hitter_totals_vs_sp[team][key] = val
                    else:
                        self.hitter_totals_vs_sp[team] = player_data

    def load_projections(self):
        try:
            self.load_pitcher_totals(self.pitcher_file_path)
            self.load_hitter_totals(self.hitter_file_path)
            self.load_hitters_projections(self.hitter_file_path)
            self.load_pitchers_projections(self.pitcher_file_path)
            self.load_games(self.pitcher_file_path)
            self.teams_dict = self.update_pitcher_positions(self.teams_dict)
        except Exception as e:
            logger.error(f"Error loading projections: {str(e)}")
            raise

    def update_pitcher_positions(self, teams_dict):
        for team, players in teams_dict.items():
            pitchers = [player for player in players if "P" in player["Position"]]
            
            if len(pitchers) == 2:
                for pitcher in pitchers:
                    if pitcher["Opener"]:
                        pitcher["Position"] = ["Opener"]
                        break  # Only change one pitcher's position

        return teams_dict

    def load_hitters_projections(self, path):
        team_order = {}  # Dictionary to track order of teams
        with open(path, encoding="utf-8-sig") as file:
            reader = csv.DictReader(self.lower_first(file))
            for row in reader:
                if not row["hbp"] or not row["hbp"].strip():
                    row["hbp"] = "0"
                if not row["cs"] or not row["cs"].strip():
                    row["cs"] = "0"
                if "2h" in row and row["2h"] == self.dh:
                    continue
                if "ipl" in row and row["ipl"] == "false":
                    continue
                team = row.get('team') or row.get('tm')
                if not row["lp"] or not row["lp"].strip():
                    # Increment team order counter
                    team_order[team] = team_order.get(team, 0) + 1
                    row["lp"] = str(team_order[team])
                if "lp" in row and float(row["lp"]) > 9:
                    continue
                if team not in self.pitcher_totals:
                    continue
                player_name = row["name"].replace("-", "#").lower()
                if "playerid" in row:
                    player_id = row["playerid"]
                else:
                    player_id = self.id_counter
                    self.id_counter += 1
                if "pos" in row:
                    position = sorted([pos for pos in row["pos"].split("/")])
                else:
                    position = ['batter']
                opp = row.get("opp_tm") or row.get("opp")
                # hfa = row.get("hfa")
                batting_order = int(row["lp"])
                
                if "pavssp" in row:
                    pavssp = float(row["pavssp%"].replace("%", '')) / 100
                else:
                    pavssp = .053 + -.007 * float(row["lp"]) + .038 * float(self.pitcher_totals[team]["OUT"])
                if "_obp" in row:
                    outs = (1 - float(row["_obp"])) * float(row["pa"])
                else:
                    outs = float(row["pa"]) - float(row["bb"]) - float(row["hbp"]) - float(row["1b"]) - float(row["2b"]) - float(row["3b"]) - float(row["hr"]) 

                if "ph%" in row:
                    pa_no_ph = (float(row["0%_ph%_fpts"]) / float(row["fpts"])) * float(row["pa"])
                    pa_vs_pen_no_ph = pa_no_ph - float(row["pavssp"])
                    ph = float(row["ph%"].replace("%", '')) / 100
                    ph_risk = 1 - ((1 - ph) ** (1 / pa_vs_pen_no_ph)) if pa_vs_pen_no_ph > 0 else 0
                else:
                    ph_risk = max(0, 1.56 + -.03 * float(row["lp"]) + -.36 * float(row["pa"]) + .006 * self.pitcher_totals[team]["OUT"])

                non_hr_hits = float(row["1b"]) + float(row["2b"]) + float(row["3b"])
                non_hr_hits_singles = float(row["1b"]) / non_hr_hits
                non_hr_hits_doubles = float(row["2b"]) / non_hr_hits
                non_hr_hits_triples = float(row["3b"]) / non_hr_hits

                hits_vs_sp = (non_hr_hits + float(row["hr"])) * pavssp
                adj_hits_vs_sp = hits_vs_sp * (self.pitcher_totals[team]["H"] / self.hitter_totals_vs_sp[team]["H"])
                hr_vs_sp = float(row["hr"]) * pavssp * (self.pitcher_totals[team]["HR"] / self.hitter_totals_vs_sp[team]["HR"])
                adj_non_hr_hits_vs_sp = adj_hits_vs_sp - hr_vs_sp
                
                single_vs_sp = adj_non_hr_hits_vs_sp * non_hr_hits_singles
                double_vs_sp = adj_non_hr_hits_vs_sp * non_hr_hits_doubles
                triple_vs_sp = adj_non_hr_hits_vs_sp * non_hr_hits_triples
                
                sb_vs_sp = float(row["sb"]) * pavssp * (self.pitcher_totals[team]["SB"] / self.hitter_totals_vs_sp[team]["SB"])
                cs_vs_sp = float(row["cs"]) * pavssp * (self.pitcher_totals[team]["CS"] / (self.hitter_totals_vs_sp[team]["CS"] + 0.0001))
                k_vs_sp = float(row["k"]) * pavssp * (self.pitcher_totals[team]["K"] / self.hitter_totals_vs_sp[team]["K"])
                bb_vs_sp = float(row["bb"]) * pavssp * (self.pitcher_totals[team]["BB"] / self.hitter_totals_vs_sp[team]["BB"])
                hbp_vs_sp = float(row["hbp"]) * pavssp * (self.pitcher_totals[team]["HBP"] / (self.hitter_totals_vs_sp[team]["HBP"] + 0.0001))
                out_vs_sp = outs * pavssp * (self.pitcher_totals[team]["OUT"] / self.hitter_totals_vs_sp[team]["OUT"])

                player_data = {
                    "Position": position[0],
                    "Name": player_name,
                    "Team": team,
                    "Opp": opp,
                    #"HFA": hfa,
                    "ID": player_id,
                    "Opp Pitcher ID": "",
                    "Opp Pitcher Name": "",
                    "In Lineup": True,
                    "Order": batting_order,
                    "PH": float(ph_risk),
                    "SP": {
                        "PA": pavssp,
                        "1B": single_vs_sp,
                        "2B": double_vs_sp,
                        "3B": triple_vs_sp,
                        "HR": hr_vs_sp,
                        "SB": sb_vs_sp,
                        "CS": cs_vs_sp,
                        "K": k_vs_sp,
                        "BB": bb_vs_sp,
                        "HBP": hbp_vs_sp,
                        "OUT": out_vs_sp
                    },
                    "RP": {
                        "PA": float(row["pa"]) - pavssp,
                        "1B": float(row["1b"]) - single_vs_sp,
                        "2B": float(row["2b"]) - double_vs_sp,
                        "3B": float(row["3b"]) - triple_vs_sp,
                        "HR": float(row["hr"]) - hr_vs_sp,
                        "SB": float(row["sb"]) - sb_vs_sp,
                        "CS": float(row["cs"]) - cs_vs_sp,
                        "K": float(row["k"]) - k_vs_sp,
                        "BB": float(row["bb"]) - bb_vs_sp,
                        "HBP": float(row["hbp"]) - hbp_vs_sp,
                        "OUT": outs - out_vs_sp
                    }
                }


                self.hitters_dict[(player_name, position[0], team)] = player_data
                if self.teams_dict[team]:
                    self.teams_dict[team].append(player_data)
                else:
                    self.teams_dict[team].append(player_data)
                    self.hitters_dict[('ph', 'ph', team)] = {
                        "Position": 'ph',
                        "Name": 'ph',
                        "Team": team,
                        "Opp": opp,
                        #"HFA": hfa,
                        "ID": -1,
                        "Opp Pitcher ID": "",
                        "Opp Pitcher Name": "",
                        "In Lineup": False,
                        "Order": -1,
                        "PH": 0.0,
                        "SP": self.replacement_hitter,
                        "RP": self.replacement_hitter
                    }
                    self.pitchers_dict[('bullpen', 'bullpen', team)] = {
                        "Position": 'bullpen',
                        "Name": 'bullpen',
                        "Team": team,
                        "Opp": opp,
                        #"HFA": hfa,
                        "Opp Pitcher ID": "",
                        "Opp Pitcher Name": "",
                        "In Lineup": True,
                        "ID": -1
                    }

    def load_pitchers_projections(self, path):
        with open(path, encoding="utf-8-sig") as file:
            reader = csv.DictReader(self.lower_first(file))
            for row in reader:
                if not row["hbp"] or not row["hbp"].strip():
                    row["hbp"] = "0"
                if not row["outs"] or not row["outs"].strip():
                    row["outs"] = float(row["ip"]) * 3
                if "2h" in row and row["2h"] == self.dh:
                    continue
                opener = False
                if "mpc" in row and row["mpc"] == "IP CAP":
                    opener = True
                player_name = row["player"].replace("-", "#").lower()
                if "playerid" in row:
                    player_id = row["playerid"]
                else:
                    player_id = self.id_counter
                    self.id_counter += 1
                position = ['P']
                team = row.get("tm") or row.get("team")
                opp = row.get("opp_tm") or row.get("opp")
                #hfa = row.get("hfa")
                ppc = 0
                mpc = 0
                if "ppc" in row and row["ppc"] == "--":
                    opener_value = row["opener"]
                    if "Yes" in opener_value:
                        # Extract the number in parentheses
                        ip_value = float(opener_value.split("(")[1].split()[0])
                        ppc = ip_value * 15
                        mpc = ppc + 15
                    else:
                        ppc = 5 * float(row["outs"])
                        mpc = 6 * float(row["outs"])
                elif "pitch count (optional)" in row:
                    ppc = float(row["pitch count (optional)"]) if row["pitch count (optional)"].strip() else 3.35 * float(row["h"]) + 5.46 * float(row["bb"]) + 4.85 * float(row["k"]) + 3.35 * (float(row["outs"]) - float(row["k"]))
                    mpc = ppc * 1.12 if ppc > 0 else 0
                else:
                    ppc = float(row["ppc"])
                    mpc = float(row["mpc"])

                player_data = {
                    "Position": position[0],
                    "Name": player_name,
                    "Team": team,
                    "Opp": opp,
                    #"HFA": hfa,
                    "Opp Pitcher ID": "",
                    "Opp Pitcher Name": "",
                    "In Lineup": True,
                    "Opener": opener,
                    "ID": player_id,
                    "HR": float(row["hr"]),
                    "K": float(row["k"]),
                    "BB": float(row["bb"]),
                    "HBP": float(row["hbp"]),
                    "PPC": ppc,
                    "MPC": mpc
                }

                self.pitchers_dict[(player_name, position[0], team)] = player_data
                self.teams_dict[team].append(player_data)

    def load_games(self, path):
        home_teams = set()
        with open(path, encoding="utf-8-sig") as file:
            reader = csv.DictReader(self.lower_first(file))
            for row in reader:
                if row['hfa'] == 'TRUE' or row['hfa'] == 'true' or row['hfa'].startswith('H') or row['hfa'].startswith('h'):
                    home_teams.add(row.get('team') or row.get('tm'))

        with open(path, encoding="utf-8-sig") as file:
            reader = csv.DictReader(self.lower_first(file))
            for row in reader:
                if row['hfa'] == 'FALSE' or row['hfa'] == 'false' or row['hfa'].startswith('A') or row['hfa'].startswith('a'):
                    away_team = row.get('tm') or row.get('team')
                    home_team = row.get('opp_tm') or row.get('opp')

                    if not any(game for game in self.games if game[0] == away_team and game[1] == home_team):
                        self.games.append((away_team, home_team))

    def run_simulation(self):
        h_results_list, p_results_list = self.simulate_games(self.games)

        return h_results_list, p_results_list

    def simulate_game_wrapper(self, game_and_sim):
        game, sim_number = game_and_sim
        away_team, home_team = game
        result = self.simulate_game(away_team, home_team, sim_number)
        return result

    def simulate_games(self, games):
        h_results_list = []
        p_results_list = []

        # Calculate optimal number of processes based on CPU cores and simulation size
        num_cpus = mp.cpu_count()
        optimal_processes = max(1, min(num_cpus, len(games)))  # Use all available CPUs
        
        # Create smaller chunks for better memory management and more even distribution
        chunk_size = max(1, min(
            self.num_sims // (optimal_processes * 20),  # Smaller chunks for more even distribution
            100  # Cap maximum chunk size
        ))
        simulation_params = [(game, i) for game in games for i in range(self.num_sims)]
        
        # Use a context manager for the pool to ensure proper cleanup
        with mp.Pool(processes=optimal_processes) as pool:
            # Use imap_unordered for better performance with large datasets
            for result in pool.imap_unordered(self.simulate_game_wrapper, simulation_params, chunksize=chunk_size):
                h_results_list.extend(result['hitter_results'])
                p_results_list.extend(result['pitcher_results'])

        return h_results_list, p_results_list

    def simulate_game(self, away_team, home_team, sim_number):
        # Initialize game state
        inning = 1
        half_inning = 0
        outs = 0
        runners = [None] * 3
        inherited_runners = [None] * 3
        runs = np.zeros(2, dtype=int)
        runs_current_inning = 0
        starter_info = [None, None]
        results_dict = {}

        # Add tracking variables for first occurrences
        first_hit = False
        first_rbi = False
        first_run = False
        first_hr = False
        first_k = False
        first_run_allowed = False

        # Add inning-specific tracking
        first_inning_complete = False
        first_three_innings_complete = False

        if not (home_team and away_team):
            raise ValueError("Unable to determine home and away teams")
        
        pitcher_stats = ["pBF", "pOuts", "pW", "pQS", "pIP", "pH", "p1B", "p2B", "p3B", "pHR", "pSB", "pCS", "pK", "pBB", "pHBP", "pR", "pPC", "In_Game", "In_Line_For_Win",
                        "pFirstInnK", "pFirst3InnK", "pFirstInnPC", "pFirst3InnPC", "pFirstInnR", "pFirst3InnR", "pFirstInnH", "pFirst3InnH", "pFirstInnBF", "pFirst3InnBF", "pFirstRunAllowed", "pFirstK"]
        hitter_stats = ["bPA", "b1B", "b2B", "b3B", "bHR", "bSB", "bCS", "bK", "bBB", "bHBP", "bR", "bRBI",
                       "bFirstInnR", "bFirst3InnR", "bFirstInnH", "bFirst3InnH", "bFirstInnHRBI", "bFirst3InnHRBI",
                       "bFirstHit", "bFirstRBI", "bFirstRun", "bFirstHR"]

        for team, index in [(away_team, 0), (home_team, 1)]:
            for player in self.teams_dict[team]:
                if 'Opener' in player['Position']:
                    continue
                elif 'P' in player['Position']:
                    starter_info[index] = (player['Name'], player['Position'], player['Team'])
                    results_dict[starter_info[index]] = {stat: (1 if stat == 'In_Game' else 0) for stat in pitcher_stats}
                else:
                    results_dict[(player['Name'], player['Position'], player['Team'])] = {stat: 0 for stat in hitter_stats}


        results_dict[('bullpen', 'bullpen', away_team)] = {stat: 0 for stat in pitcher_stats}
        results_dict[('bullpen', 'bullpen', home_team)] = {stat: 0 for stat in pitcher_stats}
        results_dict[('ph', 'ph', away_team)] = {stat: 0 for stat in hitter_stats}
        results_dict[('ph', 'ph', home_team)] = {stat: 0 for stat in hitter_stats}

        team_data = {
            0: {'lineup': self.create_lineup(away_team), 'pitcher': self.get_pitcher(away_team), 'order': 0},
            1: {'lineup': self.create_lineup(home_team), 'pitcher': self.get_pitcher(home_team), 'order': 0}
        }

        # Game loop
        while True:
            batting_team = team_data[half_inning]['lineup']
            place_in_batting_order = team_data[half_inning]['order']
            current_pitcher = team_data[1 - half_inning]['pitcher']
            
            # Track inning-specific stats
            team_key = 'home' if half_inning == 1 else 'away'
            
            # Simulate plate appearances until 3 outs
            while outs < 3:

                # check if pitcher was pulled
                if results_dict[starter_info[1 - half_inning]]['In_Game']:
                    was_pulled, inherited_runners = self.handle_pitching_change(current_pitcher, runners, inning, runs_current_inning, results_dict)

                    if was_pulled:
                        results_dict[starter_info[1 - half_inning]]['In_Game'] = 0

                        # Check if starter is in line for the win
                        if self.check_win_eligibility(inning, runs, half_inning):
                            results_dict[starter_info[1 - half_inning]]['In_Line_For_Win'] = 1

                        # Switch to bullpen pitcher
                        current_pitcher = self.pitchers_dict[('bullpen', 'bullpen', starter_info[1 - half_inning][2])]
                        team_data[1 - half_inning]['pitcher'] = current_pitcher

                current_batter = batting_team[place_in_batting_order]

                # check to see if batter gets pinch hit for or gets removed from the game
                remove = False
                if self.get_random() < 0.01: 
                    remove = True
                if current_pitcher['Name'] == 'bullpen':
                    if self.get_random() < current_batter['PH']:
                        remove = True
                else:
                    pass

                if remove:
                    if half_inning == 0: 
                        team = away_team
                    else: 
                        team = home_team
                    # replace current batter
                    current_batter = self.hitters_dict[('ph', 'ph', team)]

                    team_data[half_inning]['lineup'][place_in_batting_order] = current_batter

                # check for stolen base shenanigans
                lead_runner_index = next((i for i in range(2, -1, -1) if runners[i] is not None), None)

                if lead_runner_index is not None and lead_runner_index < 2:
                    runners, outs = self.sim_stolen_base(lead_runner_index, runners, outs, results_dict, current_pitcher)
                    if outs == 3:
                        break
                
                # sim plate appearance
                runners, outs, pa_runs, first_k, first_hit, first_rbi, first_run, first_hr, first_run_allowed = self.simulate_plate_appearance(current_batter, current_pitcher, results_dict, runners, outs, inherited_runners, starter_info, half_inning, inning, first_inning_complete, first_three_innings_complete, first_k, first_hit, first_rbi, first_run, first_hr, first_run_allowed)

                # add runs scored during plate appearance to score
                runs[half_inning] += pa_runs
                runs_current_inning += pa_runs

                # check for walk off
                if half_inning == 1 and inning >= 9 and runs[1] > runs[0]:
                    break

                # update batting order
                if place_in_batting_order == 8: place_in_batting_order = 0
                else: place_in_batting_order = place_in_batting_order + 1

            # Update inning completion flags
            if inning == 1 and half_inning == 1:
                first_inning_complete = True
            if inning == 3 and half_inning == 1:
                first_three_innings_complete = True

            # check for game over
            if (inning >= 9 and half_inning == 1 and runs[0] != runs[1]) or (inning == 9 and half_inning == 0 and runs[1] > runs[0]):
                break

            # handle end of half-inning
            outs = 0
            runs_current_inning = 0
            runners = [None] * 3
            inherited_runners = [None] * 3
            team_data[half_inning]['order'] = place_in_batting_order

            # check if starter still in line for win
            for i in range(2):
                if results_dict[starter_info[i]]['In_Line_For_Win'] == 1:
                    results_dict[starter_info[i]]['In_Line_For_Win'] = int(runs[i] > runs[1-i])

            if half_inning == 1:
                inning += 1
            half_inning = 1 - half_inning

        hitter_results = []
        pitcher_results = []

        for starter in starter_info:
            results_dict[starter]['pIP'] = round(results_dict[starter]['pOuts'] / 3, 2)
            results_dict[starter]['pERA'] = round((9 / (results_dict[starter]['pOuts'] / 3)) * results_dict[starter]['pR'], 2) if results_dict[starter]['pOuts'] > 0 else 'inf'
            if results_dict[starter]['pOuts'] >= 18 and results_dict[starter]['pR'] <= 3:
                results_dict[starter]['pQS'] = 1
            if results_dict[starter]['In_Line_For_Win']:
                results_dict[starter]['pW'] = 1

        for player, stats in results_dict.items():
            if player[0] == 'bullpen' or player[0] == 'ph': continue
            opp_team = away_team if player[2] != away_team else home_team
            if player[1] == 'P':
                stats["pH"] = stats["p1B"] + stats["p2B"] + stats["p3B"] + stats["pHR"]
                stats["pUD"] = stats["pW"] * 5 + stats["pQS"] * 5 + stats["pK"] * 3 + stats["pOuts"] - stats["pR"] * 3

                pitcher_results.append({**stats, 'player': player[0], 'team': player[2], 'opp': opp_team, 'pos': player[1], 'sim_no': sim_number})
            else:
                stats["bH"] = stats["b1B"] + stats["b2B"] + stats["b3B"] + stats["bHR"]
                stats["bHRRBI"] = stats["bH"] + stats["bR"] + stats["bRBI"]
                stats["bTB"] = stats["b1B"] + 2 * stats["b2B"] + 3 * stats["b3B"] + 4 * stats["bHR"]
                stats["bUD"] = stats["b1B"] * 3 + stats["b2B"] * 6 + stats["b3B"] * 8 + stats["bHR"] * 10 + stats["bR"] * 2 + stats["bRBI"] * 2 + stats["bBB"] * 3 + stats["bHBP"] * 3 + stats["bSB"] * 4
                hitter_results.append({**stats, 'player': player[0], 'team': player[2], 'opp': opp_team,'pos': player[1], 'sim_no': sim_number})

        return {
            'hitter_results': hitter_results,
            'pitcher_results': pitcher_results
        }

    def handle_pitching_change(self, current_pitcher, runners, inning, runs_current_inning, results_dict):
        starter_key = (current_pitcher['Name'], current_pitcher['Position'], current_pitcher['Team'])
        
        # Check if the current pitcher is the starter
        #if starter_key == self.starters[1 - half_inning]:
        pitch_count = results_dict[starter_key]['pPC']
        runs_allowed = results_dict[starter_key]['pR']
        projected_pitch_count = current_pitcher['PPC']
        max_pitch_count = current_pitcher['MPC']

        # Check for blowup (you may want to define this condition more precisely)
        blowup = runs_current_inning >= 9 - inning  # This is a simple heuristic, adjust as needed

        if self.get_random() < .0015:
            # random injury/ejection
            return True, runners.copy()
        if blowup or pitch_count >= max_pitch_count:
            # Pitcher gets pulled
            return True, runners.copy()
        elif pitch_count >= projected_pitch_count:
            # Simulate chance of being pulled
            pull_probability = 0.5 + 0.5 * (pitch_count - projected_pitch_count) / (max_pitch_count - projected_pitch_count)
            if self.get_random() < pull_probability:
                # Pitcher gets pulled
                return True, runners.copy()

        # Pitcher stays in the game
        return False, [None] * 3

    def check_win_eligibility(self, inning, runs, half_inning):
        if inning > 5:
            if half_inning == 0:
                return runs[1] > runs[0]
            else:
                return runs[0] > runs[1]
        return False

    def create_lineup(self, team):
        lineup = sorted([player for player in self.teams_dict[team] if 'P' not in player['Position']], key=lambda x: x.get('Order', float('inf')))[:9]
        return lineup

    def get_pitcher(self, team):
        pitcher = next(player for player in self.teams_dict[team] if 'P' in player['Position'])
        return pitcher

    def add_pitches(self, outcome):
        outcome_stats = {
            'hit': (3.35, 1.84),
            'bb': (5.73, 1.36),
            'k': (4.85, 1.4),
            'out': (3.38, 1.83),
            'hbp': (3.17, 1.8)
        }
        
        outcome_mean, outcome_std = outcome_stats.get(outcome, (0, 0))
        p = round(np.random.normal(outcome_mean, outcome_std))
        
        if outcome == 'bb':
            return max(p, 4)
        elif outcome == 'k':
            return max(p, 3)
        else:
            return max(p, 1)
    
    def simulate_plate_appearance(self, batter, pitcher, results_dict, runners, outs, inherited_runners, starter_info, half_inning, inning, first_inning_complete, first_three_innings_complete, first_k, first_hit, first_rbi, first_run, first_hr, first_run_allowed):
        # Log PA stat
        results_dict[(batter['Name'], batter['Position'], batter['Team'])]["bPA"] += 1
        
        # Log BF stat for pitcher
        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pBF"] += 1

        if results_dict[starter_info[1 - half_inning]]['In_Game'] == 0:
            outcome_indicator = "RP"
        else:
            outcome_indicator = "SP"
        
        # Simulate PA outcome
        outcome = self.sim_pa_outcome(batter, outcome_indicator)
        pa_runs = 0
        
        if inning == 1 and not first_inning_complete:
            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnBF"] += 1
            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnBF"] += 1
            if outcome in ['1B', '2B', '3B', 'HR']:
                results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnH"] += 1
                results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnH"] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]["bFirstInnH"] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]["bFirst3InnH"] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]["bFirstInnHRBI"] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]["bFirst3InnHRBI"] += 1
        elif inning <= 3 and not first_three_innings_complete:
            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnBF"] += 1
            if outcome in ['1B', '2B', '3B', 'HR']:
                results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnH"] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]["bFirst3InnH"] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]["bFirst3InnHRBI"] += 1

        if not first_hit and outcome in ['1B', '2B', '3B', 'HR']:
            results_dict[(batter['Name'], batter['Position'], batter['Team'])]["bFirstHit"] += 1
            first_hit = True

        handler = getattr(self, f'handle_{outcome.lower()}')
        return handler(batter, pitcher, runners, outs, results_dict, pa_runs, inherited_runners, starter_info, half_inning, outcome_indicator, inning, first_inning_complete, first_three_innings_complete, first_k, first_hit, first_rbi, first_run, first_hr, first_run_allowed)
    
    def sim_pa_outcome(self, batter, outcome_indicator):
        valid_outcomes = ['1B', '2B', '3B', 'HR', 'BB', 'HBP', 'OUT']
        prob_list = [float(batter[outcome_indicator][outcome]) for outcome in valid_outcomes]
        prob_list = np.array(prob_list) / sum(prob_list)
        choice = np.random.choice(valid_outcomes, p=prob_list)
        return choice
    
    def sim_stolen_base(self, lead_runner, runners, outs, results_dict, current_pitcher):
        runner = runners[lead_runner]
        if current_pitcher['Name'] == 'bullpen':
            runner_stats = self.hitters_dict[runner]["RP"]
        else:
            runner_stats = self.hitters_dict[runner]["SP"]
        attempt_denominator = runner_stats['1B'] + runner_stats['BB'] + runner_stats['HBP']
        success_denominator = runner_stats['SB'] + runner_stats['CS']
        
        attempt_ratio = ((runner_stats['SB'] + runner_stats['CS']) / attempt_denominator) * 0.7 if attempt_denominator > 0 else 0
        success_ratio = runner_stats['SB'] / success_denominator if success_denominator > 0 else 0
        
        if self.get_random() < attempt_ratio:
            if self.get_random() < success_ratio:
                runners[lead_runner + 1], runners[lead_runner] = runner, None
                results_dict[runner]['bSB'] += 1
            else:
                runners[lead_runner] = None
                results_dict[runner]['bCS'] += 1
                outs += 1
                results_dict[(current_pitcher['Name'], current_pitcher['Position'], current_pitcher['Team'])]['pOuts'] += 1
        
        return runners, outs

    def handle_bb(self, batter, pitcher, runners, outs, results_dict, pa_runs, inherited_runners, starter_info, half_inning, outcome_indicator, inning, first_inning_complete, first_three_innings_complete, first_k, first_hit, first_rbi, first_run, first_hr, first_run_allowed):
        # Log BB stat
        results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bBB'] += 1
        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pBB'] += 1
        pitches = self.add_pitches('bb')
        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pPC'] += pitches
        if not first_inning_complete:
            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnPC"] += pitches
            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnPC"] += pitches
        elif not first_three_innings_complete:
            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnPC"] += pitches

        # Update bases and runners
        runners = [(batter['Name'], batter['Position'], batter['Team'])] + runners
        if runners[3] != None:  # Runner on third scores
            pa_runs += 1
            results_dict[runners[3]]['bR'] += 1
            results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bRBI'] += 1
            if not first_run:
                results_dict[runners[3]]['bFirstRun'] += 1
                first_run = True    
            if not first_rbi:
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstRBI'] += 1
                first_rbi = True
            if not first_inning_complete:
                results_dict[runners[3]]['bFirstInnR'] += 1
                results_dict[runners[3]]['bFirstInnHRBI'] += 1
                results_dict[runners[3]]['bFirst3InnR'] += 1
                results_dict[runners[3]]['bFirst3InnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstInnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
            elif not first_three_innings_complete:
                results_dict[runners[3]]['bFirst3InnR'] += 1
                results_dict[runners[3]]['bFirst3InnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
            if runners[3] in inherited_runners:
                results_dict[starter_info[1 - half_inning]]['pR'] += 1
                if not first_run_allowed:
                    results_dict[starter_info[1 - half_inning]]['pFirstRunAllowed'] += 1
                    first_run_allowed = True
                if not first_inning_complete:
                    results_dict[starter_info[1 - half_inning]]["pFirstInnR"] += 1
                    results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                elif not first_three_innings_complete:
                    results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
            else:
                results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pR'] += 1
                if not first_run_allowed:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pFirstRunAllowed'] += 1
                    first_run_allowed = True
                if not first_inning_complete:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnR"] += 1
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                elif not first_three_innings_complete:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
        
        runners = runners[:3]
        
        return runners, outs, pa_runs, first_k, first_hit, first_rbi, first_run, first_hr, first_run_allowed

    def handle_hbp(self, batter, pitcher, runners, outs, results_dict, pa_runs, inherited_runners, starter_info, half_inning, outcome_indicator, inning, first_inning_complete, first_three_innings_complete, first_k, first_hit, first_rbi, first_run, first_hr, first_run_allowed):
        # Log hbp stat
        results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bHBP'] += 1
        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pHBP'] += 1
        pitches = self.add_pitches('hbp')
        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pPC'] += pitches
        if not first_inning_complete:
            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnPC"] += pitches
            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnPC"] += pitches
        elif not first_three_innings_complete:
            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnPC"] += pitches

        # Update bases and runners
        runners = [(batter['Name'], batter['Position'], batter['Team'])] + runners
        if runners[3] != None:  # Runner on third scores
            pa_runs += 1
            results_dict[runners[3]]['bR'] += 1
            results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bRBI'] += 1
            if not first_run:
                results_dict[runners[3]]['bFirstRun'] += 1
                first_run = True
            if not first_rbi:
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstRBI'] += 1
                first_rbi = True
            if not first_inning_complete:
                results_dict[runners[3]]['bFirstInnR'] += 1
                results_dict[runners[3]]['bFirstInnHRBI'] += 1
                results_dict[runners[3]]['bFirst3InnR'] += 1
                results_dict[runners[3]]['bFirst3InnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstInnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
            elif not first_three_innings_complete:
                results_dict[runners[3]]['bFirst3InnR'] += 1
                results_dict[runners[3]]['bFirst3InnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
            if runners[3] in inherited_runners:
                results_dict[starter_info[1 - half_inning]]['pR'] += 1
                if not first_run_allowed:
                    results_dict[starter_info[1 - half_inning]]['pFirstRunAllowed'] += 1
                    first_run_allowed = True
                if not first_inning_complete:
                    results_dict[starter_info[1 - half_inning]]["pFirstInnR"] += 1
                    results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                elif not first_three_innings_complete:
                    results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
            else:
                results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pR'] += 1
                if not first_run_allowed:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pFirstRunAllowed'] += 1
                    first_run_allowed = True
                if not first_inning_complete:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnR"] += 1
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                elif not first_three_innings_complete:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
        
        runners = runners[:3]
        
        return runners, outs, pa_runs, first_k, first_hit, first_rbi, first_run, first_hr, first_run_allowed
    
    def handle_extra_base_advancement(self, batter, pitcher, runners, outs, pa_runs, hit_type, lead_runner, results_dict, inherited_runners, starter_info, half_inning, outcome_indicator, first_inning_complete, first_three_innings_complete, first_hit, first_rbi, first_run, first_hr, first_run_allowed):
        if hit_type not in ['1b', '2b']:
            raise ValueError("hit_type must be either '1B' or '2B'")

        runner = runners[lead_runner]
        runner_stats = self.hitters_dict[runner][outcome_indicator]
        attempt_denominator = runner_stats['1B'] + runner_stats['BB'] + runner_stats['HBP']
        success_denominator = runner_stats['SB'] + runner_stats['CS']
        
        attempt_ratio = ((runner_stats['SB'] + runner_stats['CS']) / attempt_denominator) * 1.2 if attempt_denominator > 0 else 0
        success_ratio = runner_stats['SB'] * 1.3 / success_denominator if success_denominator > 0 else 0
        
        if self.get_random() < (attempt_ratio):
            # makes attempt to advance a base
            if self.get_random() < success_ratio:
                # successfully advances a base
                if lead_runner == 2:
                    pa_runs += 1
                    results_dict[runner]['bR'] += 1
                    results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bRBI'] += 1
                    if not first_run:
                        results_dict[runner]['bFirstRun'] += 1
                        first_run = True
                    if not first_rbi:
                        results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstRBI'] += 1
                        first_rbi = True
                    if not first_inning_complete:
                        results_dict[runner]['bFirstInnR'] += 1
                        results_dict[runner]['bFirstInnHRBI'] += 1
                        results_dict[runner]['bFirst3InnR'] += 1
                        results_dict[runner]['bFirst3InnHRBI'] += 1
                        results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstInnHRBI'] += 1
                        results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
                    elif not first_three_innings_complete:
                        results_dict[runner]['bFirst3InnR'] += 1
                        results_dict[runner]['bFirst3InnHRBI'] += 1
                        results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
                    if runner in inherited_runners:
                        results_dict[starter_info[1 - half_inning]]['pR'] += 1
                        if not first_run_allowed:
                            results_dict[starter_info[1 - half_inning]]['pFirstRunAllowed'] += 1
                            first_run_allowed = True
                        if not first_inning_complete:
                            results_dict[starter_info[1 - half_inning]]["pFirstInnR"] += 1
                            results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                        elif not first_three_innings_complete:
                            results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                    else:
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pR'] += 1
                        if not first_run_allowed:
                            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pFirstRunAllowed'] += 1
                            first_run_allowed = True
                        if not first_inning_complete:
                            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnR"] += 1
                            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                        elif not first_three_innings_complete:
                            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                    if hit_type == '1b':
                        runners[2], runners[1] = runners[1], None
                    else:
                        runners[2] = None
                else:
                    runners[2], runners[1] = runners[1], None
            else:
                # lead runner is thrown out
                if lead_runner == 1:
                    runners[1] = None
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pOuts'] += 1
                    outs += 1
                else:
                    runners[2], runners[1] = runners[1], None
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pOuts'] += 1
                    outs += 1
        else:
            # fails to make and attempt to advance a base
            pass

        return runners, outs, pa_runs, first_run, first_rbi, first_run_allowed

    def handle_1b(self, batter, pitcher, runners, outs, results_dict, pa_runs, inherited_runners, starter_info, half_inning, outcome_indicator, inning, first_inning_complete, first_three_innings_complete, first_k, first_hit, first_rbi, first_run, first_hr, first_run_allowed):
        # Log 1B stat
        results_dict[(batter['Name'], batter['Position'], batter['Team'])]['b1B'] += 1
        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['p1B'] += 1
        pitches = self.add_pitches('hit')
        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pPC'] += pitches
        if not first_inning_complete:
            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnPC"] += pitches
            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnPC"] += pitches
        elif not first_three_innings_complete:
            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnPC"] += pitches

        # Update bases and runners
        runners = [(batter['Name'], batter['Position'], batter['Team'])] + runners
        if runners[3] != None:  # Runner on third scores
            pa_runs += 1
            results_dict[runners[3]]['bR'] += 1
            results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bRBI'] += 1
            if not first_run:
                results_dict[runners[3]]['bFirstRun'] += 1
                first_run = True
            if not first_rbi:
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstRBI'] += 1
                first_rbi = True
            if not first_inning_complete:
                results_dict[runners[3]]['bFirstInnR'] += 1
                results_dict[runners[3]]['bFirstInnHRBI'] += 1
                results_dict[runners[3]]['bFirst3InnR'] += 1
                results_dict[runners[3]]['bFirst3InnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstInnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
            elif not first_three_innings_complete:
                results_dict[runners[3]]['bFirst3InnR'] += 1
                results_dict[runners[3]]['bFirst3InnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
            if runners[3] in inherited_runners:
                results_dict[starter_info[1 - half_inning]]['pR'] += 1
                if not first_run_allowed:
                    results_dict[starter_info[1 - half_inning]]['pFirstRunAllowed'] += 1
                    first_run_allowed = True
                if not first_inning_complete:
                    results_dict[starter_info[1 - half_inning]]["pFirstInnR"] += 1
                    results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                elif not first_three_innings_complete:
                    results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
            else:
                results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pR'] += 1
                if not first_run_allowed:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pFirstRunAllowed'] += 1
                    first_run_allowed = True
                if not first_inning_complete:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnR"] += 1
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                elif not first_three_innings_complete:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
        
        runners = runners[:3]

        if runners[2] != None:
            lead_runner = 2
            runners, outs, pa_runs, first_run, first_rbi, first_run_allowed = self.handle_extra_base_advancement(batter, pitcher, runners, outs, pa_runs, "1b", lead_runner, results_dict, inherited_runners, starter_info, half_inning, outcome_indicator, first_inning_complete, first_three_innings_complete, first_hit, first_rbi, first_run, first_hr, first_run_allowed)
        elif runners[1] != None: 
            lead_runner = 1
            runners, outs, pa_runs, first_run, first_rbi, first_run_allowed = self.handle_extra_base_advancement(batter, pitcher, runners, outs, pa_runs, "1b", lead_runner, results_dict, inherited_runners, starter_info, half_inning, outcome_indicator, first_inning_complete, first_three_innings_complete, first_hit, first_rbi, first_run, first_hr, first_run_allowed)
        else: pass
        
        return runners, outs, pa_runs, first_k, first_hit, first_rbi, first_run, first_hr, first_run_allowed
    
    def handle_2b(self, batter, pitcher, runners, outs, results_dict, pa_runs, inherited_runners, starter_info, half_inning, outcome_indicator, inning, first_inning_complete, first_three_innings_complete, first_k, first_hit, first_rbi, first_run, first_hr, first_run_allowed):
        # Log 2B stat
        results_dict[(batter['Name'], batter['Position'], batter['Team'])]['b2B'] += 1
        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['p2B'] += 1
        pitches = self.add_pitches('hit')
        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pPC'] += pitches
        if not first_inning_complete:
            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnPC"] += pitches
            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnPC"] += pitches
        elif not first_three_innings_complete:
            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnPC"] += pitches

        # Update bases and runners
        runners = [None, (batter['Name'], batter['Position'], batter['Team'])] + runners
        if runners[3] != None:  # Runner on second scores
            pa_runs += 1
            results_dict[runners[3]]['bR'] += 1
            results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bRBI'] += 1
            if not first_run:
                results_dict[runners[3]]['bFirstRun'] += 1
                first_run = True
            if not first_rbi:
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstRBI'] += 1
                first_rbi = True
            if not first_inning_complete:
                results_dict[runners[3]]['bFirstInnR'] += 1
                results_dict[runners[3]]['bFirstInnHRBI'] += 1
                results_dict[runners[3]]['bFirst3InnR'] += 1
                results_dict[runners[3]]['bFirst3InnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstInnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
            elif not first_three_innings_complete:
                results_dict[runners[3]]['bFirst3InnR'] += 1
                results_dict[runners[3]]['bFirst3InnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
            if runners[3] in inherited_runners:
                results_dict[starter_info[1 - half_inning]]['pR'] += 1
                if not first_run_allowed:
                    results_dict[starter_info[1 - half_inning]]['pFirstRunAllowed'] += 1
                    first_run_allowed = True
                if not first_inning_complete:
                    results_dict[starter_info[1 - half_inning]]["pFirstInnR"] += 1
                    results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                elif not first_three_innings_complete:
                    results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
            else:
                results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pR'] += 1
                if not first_run_allowed:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pFirstRunAllowed'] += 1
                    first_run_allowed = True
                if not first_inning_complete:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnR"] += 1
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                elif not first_three_innings_complete:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
        
        if runners[4] != None:  # Runner on third scores
            pa_runs += 1
            results_dict[runners[4]]['bR'] += 1
            results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bRBI'] += 1
            if not first_run:
                results_dict[runners[4]]['bFirstRun'] += 1
                first_run = True
            if not first_rbi:
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstRBI'] += 1
                first_rbi = True
            if not first_inning_complete:
                results_dict[runners[4]]['bFirstInnR'] += 1
                results_dict[runners[4]]['bFirstInnHRBI'] += 1
                results_dict[runners[4]]['bFirst3InnR'] += 1
                results_dict[runners[4]]['bFirst3InnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstInnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
            elif not first_three_innings_complete:
                results_dict[runners[4]]['bFirst3InnR'] += 1
                results_dict[runners[4]]['bFirst3InnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
            if runners[4] in inherited_runners:
                results_dict[starter_info[1 - half_inning]]['pR'] += 1
                if not first_run_allowed:
                    results_dict[starter_info[1 - half_inning]]['pFirstRunAllowed'] += 1
                    first_run_allowed = True
                if not first_inning_complete:
                    results_dict[starter_info[1 - half_inning]]["pFirstInnR"] += 1
                    results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                elif not first_three_innings_complete:
                    results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
            else:
                results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pR'] += 1
                if not first_run_allowed:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pFirstRunAllowed'] += 1
                    first_run_allowed = True
                if not first_inning_complete:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnR"] += 1
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                elif not first_three_innings_complete:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1

        runners = runners[:3]

        if runners[2] != None: 
            lead_runner = 2
            runners, outs, pa_runs, first_run, first_rbi, first_run_allowed = self.handle_extra_base_advancement(batter, pitcher, runners, outs, pa_runs, "2b", lead_runner, results_dict, inherited_runners, starter_info, half_inning, outcome_indicator, first_inning_complete, first_three_innings_complete, first_hit, first_rbi, first_run, first_hr, first_run_allowed)
        else:
            pass
        
        return runners, outs, pa_runs, first_k, first_hit, first_rbi, first_run, first_hr, first_run_allowed
    
    def handle_3b(self, batter, pitcher, runners, outs, results_dict, pa_runs, inherited_runners, starter_info, half_inning, outcome_indicator, inning, first_inning_complete, first_three_innings_complete, first_k, first_hit, first_rbi, first_run, first_hr, first_run_allowed):
        results_dict[(batter['Name'], batter['Position'], batter['Team'])]['b3B'] += 1
        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['p3B'] += 1
        pitches = self.add_pitches('hit')
        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pPC'] += pitches
        if not first_inning_complete:
            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnPC"] += pitches
            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnPC"] += pitches
        elif not first_three_innings_complete:
            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnPC"] += pitches

        # Update bases and runners
        runners = [None, None, (batter['Name'], batter['Position'], batter['Team'])] + runners
        if runners[3] != None:  # Runner on first scores
            pa_runs += 1
            results_dict[runners[3]]['bR'] += 1
            results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bRBI'] += 1
            if not first_run:
                results_dict[runners[3]]['bFirstRun'] += 1
                first_run = True
            if not first_rbi:
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstRBI'] += 1
                first_rbi = True
            if not first_inning_complete:
                results_dict[runners[3]]['bFirstInnR'] += 1
                results_dict[runners[3]]['bFirstInnHRBI'] += 1
                results_dict[runners[3]]['bFirst3InnR'] += 1
                results_dict[runners[3]]['bFirst3InnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstInnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
            elif not first_three_innings_complete:
                results_dict[runners[3]]['bFirst3InnR'] += 1
                results_dict[runners[3]]['bFirst3InnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
            if runners[3] in inherited_runners:
                results_dict[starter_info[1 - half_inning]]['pR'] += 1
                if not first_run_allowed:
                    results_dict[starter_info[1 - half_inning]]['pFirstRunAllowed'] += 1
                    first_run_allowed = True
                if not first_inning_complete:
                    results_dict[starter_info[1 - half_inning]]["pFirstInnR"] += 1
                    results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                elif not first_three_innings_complete:
                    results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
            else:
                results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pR'] += 1
                if not first_run_allowed:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pFirstRunAllowed'] += 1
                    first_run_allowed = True
                if not first_inning_complete:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnR"] += 1
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                elif not first_three_innings_complete:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
        
        if runners[4] != None:  # Runner on second scores
            pa_runs += 1
            results_dict[runners[4]]['bR'] += 1
            results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bRBI'] += 1
            if not first_run:
                results_dict[runners[4]]['bFirstRun'] += 1
                first_run = True
            if not first_rbi:
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstRBI'] += 1
                first_rbi = True
            if not first_inning_complete:
                results_dict[runners[4]]['bFirstInnR'] += 1
                results_dict[runners[4]]['bFirstInnHRBI'] += 1
                results_dict[runners[4]]['bFirst3InnR'] += 1
                results_dict[runners[4]]['bFirst3InnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstInnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
            elif not first_three_innings_complete:
                results_dict[runners[4]]['bFirst3InnR'] += 1
                results_dict[runners[4]]['bFirst3InnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
            if runners[4] in inherited_runners:
                results_dict[starter_info[1 - half_inning]]['pR'] += 1
                if not first_run_allowed:
                    results_dict[starter_info[1 - half_inning]]['pFirstRunAllowed'] += 1
                    first_run_allowed = True
                if not first_inning_complete:
                    results_dict[starter_info[1 - half_inning]]["pFirstInnR"] += 1
                    results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                elif not first_three_innings_complete:
                    results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
            else:
                results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pR'] += 1
                if not first_run_allowed:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pFirstRunAllowed'] += 1
                    first_run_allowed = True
                if not first_inning_complete:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnR"] += 1
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                elif not first_three_innings_complete:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1

        if runners[5] != None:  # Runner on third scores
            pa_runs += 1
            results_dict[runners[5]]['bR'] += 1
            results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bRBI'] += 1
            if not first_run:
                results_dict[runners[5]]['bFirstRun'] += 1
                first_run = True
            if not first_rbi:
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstRBI'] += 1
                first_rbi = True
            if not first_inning_complete:
                results_dict[runners[5]]['bFirstInnR'] += 1
                results_dict[runners[5]]['bFirstInnHRBI'] += 1
                results_dict[runners[5]]['bFirst3InnR'] += 1
                results_dict[runners[5]]['bFirst3InnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstInnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
            elif not first_three_innings_complete:
                results_dict[runners[5]]['bFirst3InnR'] += 1
                results_dict[runners[5]]['bFirst3InnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
            if runners[5] in inherited_runners:
                results_dict[starter_info[1 - half_inning]]['pR'] += 1
                if not first_run_allowed:
                    results_dict[starter_info[1 - half_inning]]['pFirstRunAllowed'] += 1
                    first_run_allowed = True
                if not first_inning_complete:
                    results_dict[starter_info[1 - half_inning]]["pFirstInnR"] += 1
                    results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                elif not first_three_innings_complete:
                    results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
            else:
                results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pR'] += 1
                if not first_run_allowed:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pFirstRunAllowed'] += 1
                    first_run_allowed = True
                if not first_inning_complete:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnR"] += 1
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                elif not first_three_innings_complete:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1

        runners = runners[:3]

        return runners, outs, pa_runs, first_k, first_hit, first_rbi, first_run, first_hr, first_run_allowed
    
    def handle_hr(self, batter, pitcher, runners, outs, results_dict, pa_runs, inherited_runners, starter_info, half_inning, outcome_indicator, inning, first_inning_complete, first_three_innings_complete, first_k, first_hit, first_rbi, first_run, first_hr, first_run_allowed):
        # Log HR stat
        pa_runs += 1
        results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bHR'] += 1
        results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bR'] += 1
        results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bRBI'] += 1

        if not first_hr:
            results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstHR'] += 1
            first_hr = True
        if not first_inning_complete:
            results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstInnR'] += 1
            results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnR'] += 1
            results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstInnHRBI'] += 1
            results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
        elif not first_three_innings_complete:
            results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnR'] += 1
            results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1

        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pHR'] += 1
        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pR'] += 1
        if not first_inning_complete:
            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnR"] += 1
            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
        elif not first_three_innings_complete:
            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1

        pitches = self.add_pitches('hit')
        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pPC'] += pitches
        if not first_inning_complete:
            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnPC"] += pitches
            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnPC"] += pitches
        elif not first_three_innings_complete:
            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnPC"] += pitches

        # Update bases and runners
        runners = [None, None, None] + runners
        if runners[3] != None:  # Runner on first scores
            pa_runs += 1
            results_dict[runners[3]]['bR'] += 1
            results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bRBI'] += 1
            if not first_run:
                results_dict[runners[3]]['bFirstRun'] += 1
                first_run = True
            if not first_rbi:
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstRBI'] += 1
                first_rbi = True
            if not first_inning_complete:
                results_dict[runners[3]]['bFirstInnR'] += 1
                results_dict[runners[3]]['bFirstInnHRBI'] += 1
                results_dict[runners[3]]['bFirst3InnR'] += 1
                results_dict[runners[3]]['bFirst3InnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstInnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
            elif not first_three_innings_complete:
                results_dict[runners[3]]['bFirst3InnR'] += 1
                results_dict[runners[3]]['bFirst3InnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
            if runners[3] in inherited_runners:
                results_dict[starter_info[1 - half_inning]]['pR'] += 1
                if not first_run_allowed:
                    results_dict[starter_info[1 - half_inning]]['pFirstRunAllowed'] += 1
                    first_run_allowed = True
                if not first_inning_complete:
                    results_dict[starter_info[1 - half_inning]]["pFirstInnR"] += 1
                    results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                elif not first_three_innings_complete:
                    results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
            else:
                results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pR'] += 1
                if not first_run_allowed:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pFirstRunAllowed'] += 1
                    first_run_allowed = True
                if not first_inning_complete:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnR"] += 1
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                elif not first_three_innings_complete:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
        
        if runners[4] != None:  # Runner on second scores
            pa_runs += 1
            results_dict[runners[4]]['bR'] += 1
            results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bRBI'] += 1
            if not first_run:
                results_dict[runners[4]]['bFirstRun'] += 1
                first_run = True
            if not first_rbi:
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstRBI'] += 1
                first_rbi = True
            if not first_inning_complete:
                results_dict[runners[4]]['bFirstInnR'] += 1
                results_dict[runners[4]]['bFirstInnHRBI'] += 1
                results_dict[runners[4]]['bFirst3InnR'] += 1
                results_dict[runners[4]]['bFirst3InnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstInnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
            elif not first_three_innings_complete:
                results_dict[runners[4]]['bFirst3InnR'] += 1
                results_dict[runners[4]]['bFirst3InnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
            if runners[4] in inherited_runners:
                results_dict[starter_info[1 - half_inning]]['pR'] += 1
                if not first_run_allowed:
                    results_dict[starter_info[1 - half_inning]]['pFirstRunAllowed'] += 1
                    first_run_allowed = True
                if not first_inning_complete:
                    results_dict[starter_info[1 - half_inning]]["pFirstInnR"] += 1
                    results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                elif not first_three_innings_complete:
                    results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
            else:
                results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pR'] += 1
                if not first_run_allowed:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pFirstRunAllowed'] += 1
                    first_run_allowed = True
                if not first_inning_complete:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnR"] += 1
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                elif not first_three_innings_complete:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1

        if runners[5] != None:  # Runner on third scores
            pa_runs += 1
            results_dict[runners[5]]['bR'] += 1
            results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bRBI'] += 1
            if not first_run:
                results_dict[runners[5]]['bFirstRun'] += 1
                first_run = True
            if not first_rbi:
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstRBI'] += 1
                first_rbi = True
            if not first_inning_complete:
                results_dict[runners[5]]['bFirstInnR'] += 1
                results_dict[runners[5]]['bFirstInnHRBI'] += 1
                results_dict[runners[5]]['bFirst3InnR'] += 1
                results_dict[runners[5]]['bFirst3InnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstInnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
            elif not first_three_innings_complete:
                results_dict[runners[5]]['bFirst3InnR'] += 1
                results_dict[runners[5]]['bFirst3InnHRBI'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
            if runners[5] in inherited_runners:
                results_dict[starter_info[1 - half_inning]]['pR'] += 1
                if not first_run_allowed:
                    results_dict[starter_info[1 - half_inning]]['pFirstRunAllowed'] += 1
                    first_run_allowed = True
                if not first_inning_complete:
                    results_dict[starter_info[1 - half_inning]]["pFirstInnR"] += 1
                    results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                elif not first_three_innings_complete:
                    results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
            else:
                results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pR'] += 1
                if not first_run_allowed:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pFirstRunAllowed'] += 1
                    first_run_allowed = True
                if not first_inning_complete:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnR"] += 1
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                elif not first_three_innings_complete:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1

        runners = runners[:3]

        return runners, outs, pa_runs, first_k, first_hit, first_rbi, first_run, first_hr, first_run_allowed
    
    def handle_out(self, batter, pitcher, runners, outs, results_dict, pa_runs, inherited_runners, starter_info, half_inning, outcome_indicator, inning, first_inning_complete, first_three_innings_complete, first_k, first_hit, first_rbi, first_run, first_hr, first_run_allowed):
        # Log Out stat for pitcher
        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pOuts'] += 1

        # Sim to see if out was a strikeout
        batter_k_per_out = batter[outcome_indicator]['K'] / batter[outcome_indicator]['OUT']
        k = self.get_random()
        if k <= batter_k_per_out:
            # Log K stat
            results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bK'] += 1
            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pK'] += 1
            if not first_k:
                results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstK"] += 1
                first_k = True
            if not first_inning_complete:
                results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnK"] += 1
                results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnK"] += 1
            elif not first_three_innings_complete:
                results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnK"] += 1

            pitches = self.add_pitches('k')
            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pPC'] += pitches
            if not first_inning_complete:
                results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnPC"] += pitches
                results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnPC"] += pitches
            elif not first_three_innings_complete:
                results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnPC"] += pitches
            out_is_k = True
        else:
            pitches = self.add_pitches('out')
            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pPC'] += pitches
            if not first_inning_complete:
                results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnPC"] += pitches
                results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnPC"] += pitches
            elif not first_three_innings_complete:
                results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnPC"] += pitches
            out_is_k = False

        outs += 1

        # If out was last out or a strikeout, no need to handle baserunning
        if outs == 3 or out_is_k:
            return runners, outs, pa_runs, first_k, first_hit, first_rbi, first_run, first_hr, first_run_allowed

        base_state = [int(runners[i] is not None) for i in range(3)]
        # Handle ball in play out
        if sum(base_state) > 0:
            r = self.get_random()
            runners, outs, pa_runs, first_run, first_rbi, first_run_allowed = self.handle_ball_in_play_out(r, base_state, batter, pitcher, runners, outs, results_dict, pa_runs, inherited_runners, starter_info, half_inning, first_inning_complete, first_three_innings_complete, first_run_allowed, first_run, first_rbi)

        return runners, outs, pa_runs, first_k, first_hit, first_rbi, first_run, first_hr, first_run_allowed

    def handle_ball_in_play_out(self, r, base_state, batter, pitcher, runners, outs, results_dict, pa_runs, inherited_runners, starter_info, half_inning, first_inning_complete, first_three_innings_complete, first_run_allowed, first_run, first_rbi):
        
        if base_state == [0, 0, 1]:  # Runner on third
            if r < 0.6:
                if self.get_random() < 0.93:
                    # Successful sac fly
                    pa_runs += 1
                    results_dict[runners[2]]['bR'] += 1
                    results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bRBI'] += 1
                    if not first_run:
                        results_dict[runners[2]]['bFirstRun'] += 1
                        first_run = True
                    if not first_rbi:
                        results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstRBI'] += 1
                        first_rbi = True
                    if not first_inning_complete:
                        results_dict[runners[2]]['bFirstInnR'] += 1
                        results_dict[runners[2]]['bFirstInnHRBI'] += 1
                        results_dict[runners[2]]['bFirst3InnR'] += 1
                        results_dict[runners[2]]['bFirst3InnHRBI'] += 1
                        results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstInnHRBI'] += 1
                        results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
                    elif not first_three_innings_complete:
                        results_dict[runners[2]]['bFirst3InnR'] += 1
                        results_dict[runners[2]]['bFirst3InnHRBI'] += 1
                        results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
                    if runners[2] in inherited_runners:
                        results_dict[starter_info[1 - half_inning]]['pR'] += 1
                        if not first_run_allowed:
                            results_dict[starter_info[1 - half_inning]]['pFirstRunAllowed'] += 1
                            first_run_allowed = True
                        if not first_inning_complete:
                            results_dict[starter_info[1 - half_inning]]["pFirstInnR"] += 1
                            results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                        elif not first_three_innings_complete:
                            results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                    else:
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pR'] += 1
                        if not first_run_allowed:
                            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pFirstRunAllowed'] += 1
                            first_run_allowed = True
                        if not first_inning_complete:
                            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnR"] += 1
                            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                        elif not first_three_innings_complete:
                            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                else:
                    # Runner thrown out at home
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pOuts'] += 1
                    outs += 1
                runners = [None, None, None]
            elif r >= 0.96:
                # Ground out, fielder's choice
                runners = [(batter['Name'], batter['Position'], batter['Team']), None, None]
        
        elif base_state == [0, 1, 0]:  # Runner on second
            if r < 0.46:
                # Runner advances to third
                runners[2], runners[1] = runners[1], None
            elif r >= 0.98:
                # Ground out, fielder's choice
                runners = [(batter['Name'], batter['Position'], batter['Team']), None, None]
        
        elif base_state == [0, 1, 1]:  # Runners on second and third
            if r < 0.5:
                # Sac fly, run scores, runner advances
                pa_runs += 1
                results_dict[runners[2]]['bR'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bRBI'] += 1
                if not first_run:
                    results_dict[runners[2]]['bFirstRun'] += 1
                    first_run = True
                if not first_rbi:
                    results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstRBI'] += 1
                    first_rbi = True
                if not first_inning_complete:
                    results_dict[runners[2]]['bFirstInnR'] += 1
                    results_dict[runners[2]]['bFirstInnHRBI'] += 1
                    results_dict[runners[2]]['bFirst3InnR'] += 1
                    results_dict[runners[2]]['bFirst3InnHRBI'] += 1
                    results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstInnHRBI'] += 1
                    results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
                elif not first_three_innings_complete:
                    results_dict[runners[2]]['bFirst3InnR'] += 1
                    results_dict[runners[2]]['bFirst3InnHRBI'] += 1
                    results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
                if runners[2] in inherited_runners:
                    results_dict[starter_info[1 - half_inning]]['pR'] += 1
                    if not first_run_allowed:
                        results_dict[starter_info[1 - half_inning]]['pFirstRunAllowed'] += 1
                        first_run_allowed = True
                    if not first_inning_complete:
                        results_dict[starter_info[1 - half_inning]]["pFirstInnR"] += 1
                        results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                    elif not first_three_innings_complete:
                        results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                else:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pR'] += 1
                    if not first_run_allowed:
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pFirstRunAllowed'] += 1
                        first_run_allowed = True
                    if not first_inning_complete:
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnR"] += 1
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                    elif not first_three_innings_complete:
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                runners = [None, None, runners[1]]
            elif r < 0.6:
                # Sac fly, run scores, no advancement
                pa_runs += 1
                results_dict[runners[2]]['bR'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bRBI'] += 1
                if not first_run:
                    results_dict[runners[2]]['bFirstRun'] += 1
                    first_run = True
                if not first_rbi:
                    results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstRBI'] += 1
                    first_rbi = True
                if not first_inning_complete:
                    results_dict[runners[2]]['bFirstInnR'] += 1
                    results_dict[runners[2]]['bFirstInnHRBI'] += 1
                    results_dict[runners[2]]['bFirst3InnR'] += 1
                    results_dict[runners[2]]['bFirst3InnHRBI'] += 1
                    results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstInnHRBI'] += 1
                    results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
                elif not first_three_innings_complete:
                    results_dict[runners[2]]['bFirst3InnR'] += 1
                    results_dict[runners[2]]['bFirst3InnHRBI'] += 1
                    results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
                if runners[2] in inherited_runners:
                    results_dict[starter_info[1 - half_inning]]['pR'] += 1
                    if not first_run_allowed:
                        results_dict[starter_info[1 - half_inning]]['pFirstRunAllowed'] += 1
                        first_run_allowed = True
                    if not first_inning_complete:
                        results_dict[starter_info[1 - half_inning]]["pFirstInnR"] += 1
                        results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                    elif not first_three_innings_complete:
                        results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                else:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pR'] += 1
                    if not first_run_allowed:
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pFirstRunAllowed'] += 1
                        first_run_allowed = True
                    if not first_inning_complete:
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnR"] += 1
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                    elif not first_three_innings_complete:
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                runners[2] = None
            elif r >= 0.98:
                # Ground out, fielder's choice, out at home
                runners = [(batter['Name'], batter['Position'], batter['Team']), None, runners[1]]

        elif base_state == [1, 0, 0]:  # Runner on first
            if r < 0.08:
                # Double play
                outs += 1
                results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pOuts'] += 1
                runners = [None, None, None]
            elif r < 0.36:
                # Fielder's choice, runner advances
                runners = [None, runners[0], None]
        
        elif base_state == [1, 0, 1]:  # Runners on first and third
            if r < 0.07:
                # Double play, run may score
                results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pOuts'] += 1
                outs += 1
                if outs < 3:
                    pa_runs += 1
                    results_dict[runners[2]]['bR'] += 1
                    if not first_run:
                        results_dict[runners[2]]['bFirstRun'] += 1
                        first_run = True
                    if not first_inning_complete:
                        results_dict[runners[2]]['bFirstInnR'] += 1
                        results_dict[runners[2]]['bFirstInnHRBI'] += 1
                        results_dict[runners[2]]['bFirst3InnR'] += 1
                        results_dict[runners[2]]['bFirst3InnHRBI'] += 1
                    elif not first_three_innings_complete:
                        results_dict[runners[2]]['bFirst3InnR'] += 1
                        results_dict[runners[2]]['bFirst3InnHRBI'] += 1
                    if runners[2] in inherited_runners:
                        results_dict[starter_info[1 - half_inning]]['pR'] += 1
                        if not first_run_allowed:
                            results_dict[starter_info[1 - half_inning]]['pFirstRunAllowed'] += 1
                            first_run_allowed = True
                        if not first_inning_complete:
                            results_dict[starter_info[1 - half_inning]]["pFirstInnR"] += 1
                            results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                        elif not first_three_innings_complete:
                            results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                    else:
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pR'] += 1
                        if not first_run_allowed:
                            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pFirstRunAllowed'] += 1
                            first_run_allowed = True
                        if not first_inning_complete:
                            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnR"] += 1
                            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                        elif not first_three_innings_complete:
                            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                runners = [None, None, None]
            elif r < 0.26:
                # Out at first, run scores, runner advances
                pa_runs += 1
                results_dict[runners[2]]['bR'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bRBI'] += 1
                if not first_run:
                    results_dict[runners[2]]['bFirstRun'] += 1
                    first_run = True
                if not first_rbi:
                    results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstRBI'] += 1
                    first_rbi = True
                if not first_inning_complete:
                    results_dict[runners[2]]['bFirstInnR'] += 1
                    results_dict[runners[2]]['bFirstInnHRBI'] += 1
                    results_dict[runners[2]]['bFirst3InnR'] += 1
                    results_dict[runners[2]]['bFirst3InnHRBI'] += 1
                    results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstInnHRBI'] += 1
                    results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
                elif not first_three_innings_complete:
                    results_dict[runners[2]]['bFirst3InnR'] += 1
                    results_dict[runners[2]]['bFirst3InnHRBI'] += 1
                    results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
                if runners[2] in inherited_runners:
                    results_dict[starter_info[1 - half_inning]]['pR'] += 1
                    if not first_run_allowed:
                        results_dict[starter_info[1 - half_inning]]['pFirstRunAllowed'] += 1
                        first_run_allowed = True
                    if not first_inning_complete:
                        results_dict[starter_info[1 - half_inning]]["pFirstInnR"] += 1
                        results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                    elif not first_three_innings_complete:
                        results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                else:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pR'] += 1
                    if not first_run_allowed:
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pFirstRunAllowed'] += 1
                        first_run_allowed = True
                    if not first_inning_complete:
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnR"] += 1
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                    elif not first_three_innings_complete:
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                runners = [None, runners[0], None]
            elif r < 0.31:
                # Advances to second, no score
                runners = [None, runners[0], runners[2]]
            elif r < 0.86:
                # Sac fly, run scores
                pa_runs += 1
                results_dict[runners[2]]['bR'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bRBI'] += 1
                if not first_run:
                    results_dict[runners[2]]['bFirstRun'] += 1
                    first_run = True
                if not first_rbi:
                    results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstRBI'] += 1
                    first_rbi = True
                if not first_inning_complete:
                    results_dict[runners[2]]['bFirstInnR'] += 1
                    results_dict[runners[2]]['bFirstInnHRBI'] += 1
                    results_dict[runners[2]]['bFirst3InnR'] += 1
                    results_dict[runners[2]]['bFirst3InnHRBI'] += 1
                    results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstInnHRBI'] += 1
                    results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
                elif not first_three_innings_complete:
                    results_dict[runners[2]]['bFirst3InnR'] += 1
                    results_dict[runners[2]]['bFirst3InnHRBI'] += 1
                    results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
                if runners[2] in inherited_runners:
                    results_dict[starter_info[1 - half_inning]]['pR'] += 1
                    if not first_run_allowed:
                        results_dict[starter_info[1 - half_inning]]['pFirstRunAllowed'] += 1
                        first_run_allowed = True
                    if not first_inning_complete:
                        results_dict[starter_info[1 - half_inning]]["pFirstInnR"] += 1
                        results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                    elif not first_three_innings_complete:
                        results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                else:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pR'] += 1
                    if not first_run_allowed:
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pFirstRunAllowed'] += 1
                        first_run_allowed = True
                    if not first_inning_complete:
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnR"] += 1
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                    elif not first_three_innings_complete:
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                runners[2] = None
        
        elif base_state == [1, 1, 0]:  # Runners on first and second
            if r < 0.08:
                # Double play, runner advances to third
                results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pOuts'] += 1
                outs += 1
                runners = [None, None, runners[1]]
            elif r < 0.3:
                # Out at first, both runners advance
                runners = [None, runners[0], runners[1]]
            elif r < 0.54:
                # Runner advances to third
                runners[2] = runners[1]
                runners[1] = None
        
        elif base_state == [1, 1, 1]:  # Bases loaded
            if r < 0.05:
                # Double play, run scores
                results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pOuts'] += 1
                outs += 1
                if outs < 3:
                    pa_runs += 1
                    results_dict[runners[2]]['bR'] += 1
                    if not first_run:
                        results_dict[runners[2]]['bFirstRun'] += 1
                        first_run = True
                    if not first_inning_complete:
                        results_dict[runners[2]]['bFirstInnR'] += 1
                        results_dict[runners[2]]['bFirstInnHRBI'] += 1
                        results_dict[runners[2]]['bFirst3InnR'] += 1
                        results_dict[runners[2]]['bFirst3InnHRBI'] += 1
                    elif not first_three_innings_complete:
                        results_dict[runners[2]]['bFirst3InnR'] += 1
                        results_dict[runners[2]]['bFirst3InnHRBI'] += 1
                    if runners[2] in inherited_runners:
                        results_dict[starter_info[1 - half_inning]]['pR'] += 1
                        if not first_run_allowed:
                            results_dict[starter_info[1 - half_inning]]['pFirstRunAllowed'] += 1
                            first_run_allowed = True
                        if not first_inning_complete:
                            results_dict[starter_info[1 - half_inning]]["pFirstInnR"] += 1
                            results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                        elif not first_three_innings_complete:
                            results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                    else:
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pR'] += 1
                        if not first_run_allowed:
                            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pFirstRunAllowed'] += 1
                            first_run_allowed = True
                        if not first_inning_complete:
                            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnR"] += 1
                            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                        elif not first_three_innings_complete:
                            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                    runners = [None, None, runners[1]]
                else:
                    runners = [None, None, None]
            elif r < 0.17:
                # Out at first, run may score
                runners = [None, runners[0], runners[1]]
                if self.get_random() < 0.95:
                    pa_runs += 1
                    results_dict[runners[2]]['bR'] += 1
                    results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bRBI'] += 1
                    if not first_run:
                        results_dict[runners[2]]['bFirstRun'] += 1
                        first_run = True
                    if not first_rbi:
                        results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstRBI'] += 1
                        first_rbi = True
                    if not first_inning_complete:
                        results_dict[runners[2]]['bFirstInnR'] += 1
                        results_dict[runners[2]]['bFirstInnHRBI'] += 1
                        results_dict[runners[2]]['bFirst3InnR'] += 1
                        results_dict[runners[2]]['bFirst3InnHRBI'] += 1
                        results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstInnHRBI'] += 1
                        results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
                    elif not first_three_innings_complete:
                        results_dict[runners[2]]['bFirst3InnR'] += 1
                        results_dict[runners[2]]['bFirst3InnHRBI'] += 1
                        results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
                    if runners[2] in inherited_runners:
                        results_dict[starter_info[1 - half_inning]]['pR'] += 1
                        if not first_run_allowed:
                            results_dict[starter_info[1 - half_inning]]['pFirstRunAllowed'] += 1
                            first_run_allowed = True
                        if not first_inning_complete:
                            results_dict[starter_info[1 - half_inning]]["pFirstInnR"] += 1
                            results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                        elif not first_three_innings_complete:
                            results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                    else:
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pR'] += 1
                        if not first_run_allowed:
                            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pFirstRunAllowed'] += 1
                            first_run_allowed = True
                        if not first_inning_complete:
                            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnR"] += 1
                            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                        elif not first_three_innings_complete:
                            results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                else:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pOuts'] += 1
                    outs += 1  # Double play at home
            elif r < 0.5:
                # Sac, run scores, runner advances to third
                pa_runs += 1
                results_dict[runners[2]]['bR'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bRBI'] += 1
                if not first_run:
                    results_dict[runners[2]]['bFirstRun'] += 1
                    first_run = True
                if not first_rbi:
                    results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstRBI'] += 1
                    first_rbi = True
                if not first_inning_complete:
                    results_dict[runners[2]]['bFirstInnR'] += 1
                    results_dict[runners[2]]['bFirstInnHRBI'] += 1
                    results_dict[runners[2]]['bFirst3InnR'] += 1
                    results_dict[runners[2]]['bFirst3InnHRBI'] += 1
                    results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstInnHRBI'] += 1
                    results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
                elif not first_three_innings_complete:
                    results_dict[runners[2]]['bFirst3InnR'] += 1
                    results_dict[runners[2]]['bFirst3InnHRBI'] += 1
                    results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
                if runners[2] in inherited_runners:
                    results_dict[starter_info[1 - half_inning]]['pR'] += 1
                    if not first_run_allowed:
                        results_dict[starter_info[1 - half_inning]]['pFirstRunAllowed'] += 1
                        first_run_allowed = True
                    if not first_inning_complete:
                        results_dict[starter_info[1 - half_inning]]["pFirstInnR"] += 1
                        results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                    elif not first_three_innings_complete:
                        results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                else:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pR'] += 1
                    if not first_run_allowed:
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pFirstRunAllowed'] += 1
                        first_run_allowed = True
                    if not first_inning_complete:
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnR"] += 1
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                    elif not first_three_innings_complete:
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                runners = [runners[0], None, runners[1]]
            elif r < 0.72:
                # Sac, run scores, no advancement
                pa_runs += 1
                results_dict[runners[2]]['bR'] += 1
                results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bRBI'] += 1
                if not first_run:
                    results_dict[runners[2]]['bFirstRun'] += 1
                    first_run = True
                if not first_rbi:
                    results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstRBI'] += 1
                    first_rbi = True
                if not first_inning_complete:
                    results_dict[runners[2]]['bFirstInnR'] += 1
                    results_dict[runners[2]]['bFirstInnHRBI'] += 1
                    results_dict[runners[2]]['bFirst3InnR'] += 1
                    results_dict[runners[2]]['bFirst3InnHRBI'] += 1
                    results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirstInnHRBI'] += 1
                    results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
                elif not first_three_innings_complete:
                    results_dict[runners[2]]['bFirst3InnR'] += 1
                    results_dict[runners[2]]['bFirst3InnHRBI'] += 1
                    results_dict[(batter['Name'], batter['Position'], batter['Team'])]['bFirst3InnHRBI'] += 1
                if runners[2] in inherited_runners:
                    results_dict[starter_info[1 - half_inning]]['pR'] += 1
                    if not first_run_allowed:
                        results_dict[starter_info[1 - half_inning]]['pFirstRunAllowed'] += 1
                        first_run_allowed = True
                    if not first_inning_complete:
                        results_dict[starter_info[1 - half_inning]]["pFirstInnR"] += 1
                        results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                    elif not first_three_innings_complete:
                        results_dict[starter_info[1 - half_inning]]["pFirst3InnR"] += 1
                else:
                    results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pR'] += 1
                    if not first_run_allowed:
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]['pFirstRunAllowed'] += 1
                        first_run_allowed = True
                    if not first_inning_complete:
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirstInnR"] += 1
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                    elif not first_three_innings_complete:
                        results_dict[(pitcher['Name'], pitcher['Position'], pitcher['Team'])]["pFirst3InnR"] += 1
                runners[2] = None
        
        return runners, outs, pa_runs, first_run, first_rbi, first_run_allowed

    def process_results(self, h_results_list, p_results_list, game_results_list):
        cols = ['player', 'team', 'PA', 'H', '1B', '2B', '3B', 'HR', 'TB', 'R', 'RBI', 'HRRBI', 'SB', 'CS', 'BB', 'K', 'HBP', 'UD', 'sim_no']
        cols_pitcher = ['player', 'team', 'BF', 'Outs', 'W', 'IP', 'ERA', 'QS', 'R', 'H', '1B', '2B', '3B', 'HR', 'K', 'BB', 'HBP', 'PC', 'UD', 'sim_no']

        sim_batter_stats = pd.DataFrame(h_results_list, columns=cols)
        sim_pitcher_stats = pd.DataFrame(p_results_list, columns=cols_pitcher)
        sim_game_stats = pd.DataFrame(game_results_list)

        self.save_results(sim_batter_stats, sim_pitcher_stats, sim_game_stats)

    def save_results(self, sim_batter_stats, sim_pitcher_stats, sim_game_stats):
        try:
            path = Path(__file__).parent.parent
            sim_batter_stats.to_csv(path / 'batter.sim.results.csv', index=False)
            sim_pitcher_stats.to_csv(path / 'pitcher.sim.results.csv', index=False)
            sim_game_stats.to_csv(path / 'game.sim.results.csv', index=False)
            logger.info("Results saved successfully")
        except Exception as e:
            logger.error(f"Error saving results: {str(e)}")
            raise