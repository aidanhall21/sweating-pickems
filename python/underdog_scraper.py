import requests
import pandas as pd
import json
import logging
import os

class UnderdogScraper:
    def __init__(self, session_id=None):
        self.ud_pickem_url = "https://api.underdogfantasy.com/v2/pickem_search/search_results?sport_id=MLB"
        self.ud_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/",
            "Accept": "application/json"
        }
        self.underdog_props = None
        self.logger = logging.getLogger(__name__)
        # Add path for storing props data
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        self.session_id = session_id
        if session_id:
            self.session_dir = os.path.join(self.data_dir, 'sessions', session_id)
            self.props_file = os.path.join(self.session_dir, 'underdog_props.json')
        else:
            self.session_dir = None
            self.props_file = os.path.join(self.data_dir, 'underdog_props.json')

    def fetch_data(self):
        try:
            ud_pickem_response = requests.get(self.ud_pickem_url, headers=self.ud_headers)
            ud_pickem_response.raise_for_status()
            return ud_pickem_response.json()
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch data: {str(e)}")
            raise

    def combine_data(self, pickem_data):
        appearances = pd.DataFrame(pickem_data["appearances"])
        games = pd.DataFrame(pickem_data["games"])
        over_under_lines = pd.DataFrame(pickem_data["over_under_lines"])
        return appearances, games, over_under_lines

    def process_data(self, appearances, games, over_under_lines):
        appearances = appearances.rename(columns={"id": "appearance_id"}).drop(
            columns=[
                "badges",
                "lineup_status_id",
                "match_type",
                "sort_by",
                "type",
                "position_id"
            ],
            errors='ignore'
        )
        games = games.rename(columns={"id": "match_id"}).drop(
            columns=[
                "away_team_score",
                "home_team_score",
                "manually_created",
                "match_progress",
                "period",
                "rescheduled_from",
                "season_type",
                "status",
                "title_suffix",
                "type",
                "year"
            ],
            errors='ignore'
        )
        appearances_games = appearances.merge(games, on=["match_id"], how="left")

        # Reset index before exploding to avoid duplicate index issues
        over_under_lines = over_under_lines.drop(
            columns=[
                "expires_at",
                "line_type",
                "live_event",
                "live_event_stat",
                "non_discounted_stat_value",
                "rank",
                "sort_by",
                "status"
            ],
            errors='ignore'
        ).reset_index(drop=True)
        over_under_lines_expanded = over_under_lines.explode("options")
        
        # Apply json_normalize to the 'options' column
        options_df = pd.json_normalize(over_under_lines_expanded["options"])
        
        # Concatenate the expanded DataFrame with the normalized options
        over_under_lines_expanded = pd.concat([over_under_lines_expanded.drop("options", axis=1).reset_index(drop=True), 
                                            options_df.rename(columns={"id": "options_id"}).reset_index(drop=True)], axis=1)

        over_under_lines_expanded["appearance_id"] = over_under_lines_expanded["over_under"].apply(lambda x: x["appearance_stat"]["appearance_id"])
        over_under_lines_expanded["display_stat"] = over_under_lines_expanded["over_under"].apply(lambda x: x["appearance_stat"]["display_stat"])
        over_under_lines_expanded["has_alternates"] = over_under_lines_expanded["over_under"].apply(lambda x: x["has_alternates"])
        over_under_lines_expanded["stat_name"] = over_under_lines_expanded["over_under"].apply(lambda x: x["appearance_stat"]["stat"])


        over_under_lines_expanded = over_under_lines_expanded.drop(
            columns=[
                "over_under",
                "american_price",
                "decimal_price",
                "type"
            ],
            errors='ignore'
        )

        # Filter out period_first_pitch_of_game_strike stats before merging
        over_under_lines_filtered = over_under_lines_expanded[over_under_lines_expanded['stat_name'] != 'period_first_pitch_of_game_strike']
        underdog_props = over_under_lines_filtered.merge(appearances_games, on="appearance_id", how="left")

        return underdog_props

    def apply_name_corrections(self, df):
        name_corrections = {
            "José Ramírez": "Jose Ramirez",
            "Adolis García": "Adolis Garcia",
            "Ben Rice": "Benjamin Rice",
            "Andrés Giménez": "Andres Gimenez",
            "Angel Martínez": "Angel Martinez",
            "Eloy Jiménez": "Eloy Jimenez",
            "Brooks Baldwin": "Riley Baldwin",
            "Jeremy Peña": "Jeremy Pena",
            "Joshua Palacios": "Josh Palacios",
            "Nacho Alvarez": "Ignacio Alvarez",
            "Eugenio Suárez": "Eugenio Suarez",
            "Harold Ramírez": "Harold Ramirez",
            "Lourdes Gurriel": "Lourdes Gurriel Jr.",
            "Andy Ibáñez": "Andy Ibanez",
            "Wenceel Pérez": "Wenceel Perez",
            "Luis García": "Luis Garcia",
            "Teoscar Hernández": "Teoscar Hernandez",
            "Elias Díaz": "Elias Diaz",
            "Ramón Urías": "Ramon Urias",
            "Leo Jiménez": "Leo Jimenez",
            "Yandy Díaz": "Yandy Diaz",
            "Jesús Sánchez": "Jesus Sanchez",
            "Vidal Bruján": "Vidal Brujan",
            "José Caballero": "Jose Caballero",
            "Christian Vázquez": "Christian Vazquez",
            "Mauricio Dubón": "Mauricio Dubon",
            "Roddery Muñoz": "Roddery Munoz",
            "Alí Sánchez": "Ali Sanchez",
            "Cristopher Sánchez": "Cristopher Sanchez",
            "Carlos Narváez": "Carlos Narvaez",
            "Pablo López": "Pablo Lopez",
            "Gary Sánchez": "Gary Sanchez",
            "Pedro Pagés": "Pedro Pages",
            "JJ Bleday": "J.J. Bleday",
            "Luis L. Ortiz": "Luis Ortiz",
            "Javier Báez": "Javier Baez",
            "José Ureña": "Jose Urena",
            "Randy Vásquez": "Randy Vasquez",
            "José Berríos": "Jose Berrios",
            "Carlos Rodón": "Carlos Rodon",
            "Martín Pérez": "Martin Perez",
            "José Soriano": "Jose Soriano",
            "Jerar Encarnación": "Jerar Encarnacion",
            "Yariel Rodríguez": "Yariel Rodriguez",
            "Pedro León": "Pedro Leon",
            "Zach Dezenzo": "Zachary Dezenzo",
            "Romy González": "Romy Gonzalez",
            "Michael King": "Mike King",
            "Ramón Laureano": "Ramon Laureano",
            "Albert Suárez": "Albert Suarez",
            "Nasim Nuñez": "Nasim Nunez",
            "José Tena": "Jose Tena",
            "Julio Rodríguez": "Julio Rodriguez",
            "Michael Harris": "Michael Harris II",
            "Andrés Chaparro": "Andres Chaparro",
            "Emilio Pagán": "Emilio Pagan",
            "Jack López": "Jack Lopez",
            "Reynaldo López": "Reynaldo Lopez",
            "Domingo Germán": "Domingo German",
            "Iván Herrera": "Ivan Herrera",
            "Jasson Domínguez": "Jasson Dominguez",
            "T.J. Friedl": "TJ Friedl",
            "Josh Smith": "Josh H. Smith",
            "Samuel Aldegheri": "Sam Aldegheri",
            "Ranger Suárez": "Ranger Suarez",
            "José Suárez": "Jose Suarez",
            "José Fermín": "Jose Fermin",
            "Luis Urías": "Luis Urias",
            "Josh H. Smith": "Josh Smith",
            "J.J. Bleday": "JJ Bleday",
            "Isiah Kiner-Falefa": "Isiah Kiner-Falefa",
            "Victor Scott": "Victor Scott II",
            "José Azócar": "Jose Azocar",
            "Luis Angel Acuña": "Luisangel Acuna",
            "Luis Garcia": "Luis Garcia Jr.",
            "Oscar González": "Oscar Gonzalez",
            "Benjamin Rice": "Ben Rice"
        }
        df["selection_header"] = df["selection_header"].map(name_corrections).fillna(df["selection_header"])
        return df

    def save_props_to_file(self, props):
        """Save props data to a JSON file"""
        try:
            # Create data directory if it doesn't exist
            if self.session_id:
                os.makedirs(self.session_dir, exist_ok=True)
            else:
                os.makedirs(self.data_dir, exist_ok=True)
            
            # Convert NaN values to None (which becomes null in JSON)
            def clean_nan(obj):
                if isinstance(obj, dict):
                    return {k: clean_nan(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [clean_nan(item) for item in obj]
                elif pd.isna(obj):  # This catches both np.nan and pd.NA
                    return None
                return obj
            
            cleaned_props = clean_nan(props)
            
            with open(self.props_file, 'w') as f:
                json.dump(cleaned_props, f)
            self.logger.info(f"Props data saved to {self.props_file}")
        except Exception as e:
            self.logger.error(f"Error saving props data: {str(e)}")
            raise

    def scrape(self):
        try:
            self.logger.info("Starting Underdog scraping process")
            pickem_data = self.fetch_data()
            appearances, games, over_under_lines = self.combine_data(pickem_data)
            self.underdog_props = self.process_data(appearances, games, over_under_lines)

            # self.underdog_props = self.apply_name_corrections(underdog_props)

            props_data = self.underdog_props.to_dict('records')
            self.save_props_to_file(props_data)  # Save the props data to file

            self.logger.info(f"Scraping completed. {len(self.underdog_props)} props retrieved.")
            return props_data
        except Exception as e:
            self.logger.error(f"Error during scraping process: {str(e)}")
            raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scraper = UnderdogScraper()
    try:
        props = scraper.scrape()
        print(json.dumps(props))
    except Exception as e:
        print(f"Error: {str(e)}")