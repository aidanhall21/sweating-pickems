#!/usr/bin/env python3
import os
import sys
import logging
import argparse

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from python.underdog_scraper import UnderdogScraper

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Fetch Underdog props')
    parser.add_argument('--session-id', help='Session ID for storing props in a session-specific directory')
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    scraper = UnderdogScraper(session_id=args.session_id)
    try:
        props = scraper.scrape()
        # Props are automatically saved to data/props.json by the scraper
        sys.exit(0)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1) 