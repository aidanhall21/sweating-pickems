#!/usr/bin/env python3
import sys
import pandas as pd
import json

def validate_hitter_file(file_path):
    """
    Validates the hitter projections CSV file.
    Rules:
    1. Only HBP and CS columns are allowed to have blank values
    
    Returns a dictionary with validation results.
    """
    try:
        # Read the CSV file, skipping the instruction lines (starting with #)
        hitters_df = pd.read_csv(file_path, comment='#', on_bad_lines='skip')

        # Check for 9 hitters per team
        # Only count rows where IPL is TRUE if IPL column exists
        # Skip teams with integer values or names less than 2 characters
        if 'IPL' in hitters_df.columns:
            #hitters_df = hitters_df.iloc[:-1]
            # Filter to only include rows where IPL is TRUE and 2H is not 2
            filtered_df = hitters_df[
                (hitters_df['IPL'].astype(str).str.upper() == 'TRUE') & 
                (~hitters_df['2H'].isin([2, '2']))
            ]
        else:
            filtered_df = hitters_df
        
        # Check for required columns - OPP or OPP_TM is acceptable
        base_required_columns = ['NAME', 'TEAM', 'LP', 'PA', '1B', '2B', '3B', 'HR', 'K', 'BB', 'SB']
        missing_columns = [col for col in base_required_columns if col not in filtered_df.columns]
        
        # Check for either OPP or OPP_TM
        has_opp = 'OPP' in filtered_df.columns
        if has_opp:
            base_required_columns.append('OPP')
        has_opp_tm = 'OPP_TM' in filtered_df.columns
        if has_opp_tm:
            base_required_columns.append('OPP_TM')
        
        if not (has_opp or has_opp_tm):
            missing_columns.append('OPP/OPP_TM')
        
        if missing_columns:
            return {
                'valid': False,
                'message': f"Missing required columns in hitter file: {', '.join(missing_columns)}"
            }
        
        # Find rows with blank values in required columns
        invalid_rows = []
        for idx, row in filtered_df.iterrows():
            blank_cols = [col for col in base_required_columns if pd.isna(row[col]) or str(row[col]).strip() == '']
            if blank_cols:
                invalid_rows.append({
                    'row': idx + 2,  # +2 to account for 0-indexing and header row
                    'player': row['NAME'] if not pd.isna(row['NAME']) else f"Row {idx + 2}",
                    'blank_columns': blank_cols
                })
        
        if invalid_rows:
            return {
                'valid': False,
                'message': "Found blank values in required columns",
                'details': invalid_rows
            }
        
        # Filter out teams with invalid names (integers or names less than 2 chars)
        valid_teams = []
        for team in filtered_df['TEAM'].unique():
            # Skip if team is an integer
            try:
                int(team)
                continue  # Skip this team if it can be converted to int
            except (ValueError, TypeError):
                pass
            
            # Skip if team name is less than 2 characters
            if isinstance(team, str) and len(team) < 2:
                continue
                
            valid_teams.append(team)
        
        team_counts = filtered_df[filtered_df['TEAM'].isin(valid_teams)]['TEAM'].value_counts()
        invalid_teams = [(team, count) for team, count in team_counts.items() if count != 9]
        
        if invalid_teams:
            return {
                'valid': False,
                'message': "Each team must have exactly 9 hitters",
                'details': [f"{team}: {count} hitters" for team, count in invalid_teams]
            }
        
        # Check for duplicate lineup positions within teams
        has_lp = 'LP' in hitters_df.columns
        if has_lp:
            for team in filtered_df['TEAM'].unique():
                team_df = filtered_df[filtered_df['TEAM'] == team]
                lp_values = team_df['LP'].dropna().astype(int)
                if len(lp_values) != len(lp_values.unique()):
                    return {
                        'valid': False,
                        'message': f"Team {team} has duplicate lineup positions",
                        'details': f"Each team must have unique lineup positions (1-9)"
                    }
        
        return {'valid': True, 'message': "Hitter file validation passed"}
    
    except Exception as e:
        return {'valid': False, 'message': f"Error validating hitter file: {str(e)}"}

def validate_pitcher_file(file_path):
    """
    Validates the pitcher projections CSV file.
    Rules:
    1. Must have data in EITHER IP or OUTS columns (both don't need to have data)
    2. Only HBP and Pitch Count columns are allowed to have blank values
    3. HFA column must contain valid values (TRUE/true/H*/h* or FALSE/false/A*/a*)
    
    Returns a dictionary with validation results.
    """
    try:
        # Read the CSV file, skipping the instruction lines (starting with #)
        pitchers_df = pd.read_csv(file_path, comment='#', on_bad_lines='skip')
        
        # If MPC column exists, filter out rows where "2H" is 2 or "2" or TEAM is invalid
        if 'MPC' in pitchers_df.columns and '2H' in pitchers_df.columns:
            #pitchers_df = pitchers_df.iloc[:-1]
            # Create mask for rows to keep
            valid_2h_mask = ~pitchers_df['2H'].isin([2, '2'])
            
            # Filter out teams with invalid names (integers or names less than 2 chars)
            valid_team_mask = pitchers_df['TEAM'].apply(lambda team: 
                not (
                    # Not an integer
                    (isinstance(team, (int, float)) or (isinstance(team, str) and team.isdigit())) or
                    # Not a short string
                    (isinstance(team, str) and len(team) < 2)
                )
            )
            
            # Apply filters
            pitchers_df = pitchers_df[valid_2h_mask & valid_team_mask]
        
        # Check for required columns - OPP or OPP_TM is acceptable
        base_required_columns = ['PLAYER', 'TEAM', 'HFA', 'K', 'BB', 'H', 'HR']
        missing_columns = [col for col in base_required_columns if col not in pitchers_df.columns]
        
        # Check for either OPP or OPP_TM
        has_opp = 'OPP' in pitchers_df.columns
        if has_opp:
            base_required_columns.append('OPP')
        has_opp_tm = 'OPP_TM' in pitchers_df.columns
        if has_opp_tm:
            base_required_columns.append('OPP_TM')
        
        if not (has_opp or has_opp_tm):
            missing_columns.append('OPP/OPP_TM')
        
        # Check that either IP or OUTS is present as a column
        ip_outs_present = False
        if 'IP' in pitchers_df.columns:
            ip_outs_present = True
        if 'OUTS' in pitchers_df.columns:
            ip_outs_present = True
            
        if not ip_outs_present:
            missing_columns.append('IP/OUTS')
        
        if missing_columns:
            return {
                'valid': False,
                'message': f"Missing required columns in pitcher file: {', '.join(missing_columns)}"
            }
        
        # Check for valid HFA values
        if 'HFA' in pitchers_df.columns:
            invalid_hfa_rows = []
            for idx, row in pitchers_df.iterrows():
                hfa_value = str(row['HFA']).strip()
                if pd.isna(row['HFA']) or hfa_value == '':
                    invalid_hfa_rows.append({
                        'row': idx + 2,
                        'player': row['PLAYER'] if not pd.isna(row['PLAYER']) else f"Row {idx + 2}",
                        'error': 'HFA value is blank'
                    })
                elif not (hfa_value.upper() == 'TRUE' or 
                          hfa_value.upper() == 'FALSE' or 
                          hfa_value.upper().startswith('H') or 
                          hfa_value.upper().startswith('A')):
                    invalid_hfa_rows.append({
                        'row': idx + 2,
                        'player': row['PLAYER'] if not pd.isna(row['PLAYER']) else f"Row {idx + 2}",
                        'error': f'Invalid HFA value: "{hfa_value}". Must be TRUE/true/H*/h* or FALSE/false/A*/a*'
                    })
            
            if invalid_hfa_rows:
                return {
                    'valid': False,
                    'message': "Found invalid HFA values",
                    'details': invalid_hfa_rows
                }
        
        invalid_rows = []
        for idx, row in pitchers_df.iterrows():
            # Check for required columns with blank values (excluding IP/OUTS which are handled separately)
            blank_cols = [col for col in base_required_columns if pd.isna(row[col]) or str(row[col]).strip() == '']
            
            # Special check for IP/OUTS - at least one must have data
            ip_outs_blank = True
            if 'IP' in pitchers_df.columns and not (pd.isna(row['IP']) or str(row['IP']).strip() == ''):
                ip_outs_blank = False
            if 'OUTS' in pitchers_df.columns and not (pd.isna(row['OUTS']) or str(row['OUTS']).strip() == ''):
                ip_outs_blank = False
                
            if ip_outs_blank:
                blank_cols.append('IP/OUTS')
            
            if blank_cols:
                invalid_rows.append({
                    'row': idx + 2,  # +2 to account for 0-indexing and header row
                    'player': row['PLAYER'] if not pd.isna(row['PLAYER']) else f"Row {idx + 2}",
                    'blank_columns': blank_cols
                })
        
        if invalid_rows:
            return {
                'valid': False,
                'message': "Found blank values in required columns",
                'details': invalid_rows
            }
        
        return {'valid': True, 'message': "Pitcher file validation passed"}
    
    except Exception as e:
        return {'valid': False, 'message': f"Error validating pitcher file: {str(e)}"}

def validate_files(hitter_path, pitcher_path):
    """
    Validates both hitter and pitcher files.
    
    Returns a dictionary with validation results.
    """
    hitter_validation = validate_hitter_file(hitter_path)
    pitcher_validation = validate_pitcher_file(pitcher_path)
    
    # Check for consistent teams across both files
    if hitter_validation['valid'] and pitcher_validation['valid']:
        try:
            hitters_df = pd.read_csv(hitter_path, comment='#', on_bad_lines='skip')
            pitchers_df = pd.read_csv(pitcher_path, comment='#', on_bad_lines='skip')

            if 'IPL' in hitters_df.columns:
                #hitters_df = hitters_df.iloc[:-1]
                # Filter to only include rows where IPL is TRUE and 2H is not 2
                hitters_df = hitters_df[
                    (hitters_df['IPL'].astype(str).str.upper() == 'TRUE') & 
                    (~hitters_df['2H'].isin([2, '2']))
                ]
            else:
                pass

            # If MPC column exists, filter out rows where "2H" is 2 or "2" or TEAM is invalid
            if 'MPC' in pitchers_df.columns and '2H' in pitchers_df.columns:
                #pitchers_df = pitchers_df.iloc[:-1]
                # Create mask for rows to keep
                valid_2h_mask = ~pitchers_df['2H'].isin([2, '2'])
                
                # Filter out teams with invalid names (integers or names less than 2 chars)
                valid_team_mask = pitchers_df['TEAM'].apply(lambda team: 
                    not (
                        # Not an integer
                        (isinstance(team, (int, float)) or (isinstance(team, str) and team.isdigit())) or
                        # Not a short string
                        (isinstance(team, str) and len(team) < 2)
                    )
                )
                
                # Apply filters
                pitchers_df = pitchers_df[valid_2h_mask & valid_team_mask]
            
            hitter_teams = set(hitters_df['TEAM'].unique())
            pitcher_teams = set(pitchers_df['TEAM'].unique())
            
            missing_pitcher_teams = hitter_teams - pitcher_teams
            missing_hitter_teams = pitcher_teams - hitter_teams
            
            if missing_pitcher_teams:
                return {
                    'valid': False,
                    'message': f"Teams in hitter file without pitchers: {', '.join(missing_pitcher_teams)}"
                }
            
            if missing_hitter_teams:
                return {
                    'valid': False,
                    'message': f"Teams in pitcher file without hitters: {', '.join(missing_hitter_teams)}"
                }
            
        except Exception as e:
            return {'valid': False, 'message': f"Error validating team consistency: {str(e)}"}
    
    if not hitter_validation['valid']:
        return hitter_validation
    
    if not pitcher_validation['valid']:
        return pitcher_validation
    
    return {'valid': True, 'message': "All validation checks passed"}

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({'valid': False, 'message': "Missing file paths"}))
        sys.exit(1)
    
    hitter_path = sys.argv[1]
    pitcher_path = sys.argv[2]
    
    validation_result = validate_files(hitter_path, pitcher_path)
    print(json.dumps(validation_result))
    
    if not validation_result['valid']:
        sys.exit(1)
    else:
        sys.exit(0) 