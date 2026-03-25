
from __future__ import annotations
import requests
import json
import os
import urllib3

# Disable insecure request warnings for development
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Default to the production Render server for the best experience.
# To use a local server for testing, set RELMBAG_REMOTE=false
USE_REMOTE = os.environ.get("RELMBAG_REMOTE", "true").lower() == "true"
SERVER_URL = "https://relmbag-server.onrender.com" if USE_REMOTE else "http://localhost:5050"

def safe_request(method: str, endpoint: str, **kwargs) -> requests.Response:
    """
    Makes a request to the server with a timeout and handles exceptions.
    """
    url = f"{SERVER_URL}/{endpoint}"
    try:
        # FIX: Disable SSL verification for development environments if needed
        # Increased timeout to 120s for Render spin-up/slow response
        response = requests.request(method, url, timeout=120, verify=False, **kwargs)
        print(f"[DEBUG] {method.upper()} {url} - Status: {response.status_code}")
        response.raise_for_status()  # Raise an exception for bad status codes
        return response
    except Exception as error:
        print(f"[ERROR] Network request failed for {method.upper()} {url}: {error}")
        raise

def safe_json(response: requests.Response) -> dict | None:
    """
    Safely decodes a JSON response.
    """
    try:
        return response.json()
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to decode JSON response: {e}")
        return None
