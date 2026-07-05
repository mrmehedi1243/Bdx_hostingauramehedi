import requests
from google_play_scraper import app

def AuToUpDaTE():
    api_url = "https://auto-update-devil.vercel.app/"
    try:
        resp = requests.get(api_url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        server_url = data["server_url"]
        ob_version = data["latest_release_version"]
        version = data["play_version"] 
        return server_url, ob_version, version
    except Exception as e:
        print(f"Auto-update API failed: {e}")
        sys.exit(1)