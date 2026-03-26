
from __future__ import annotations
import requests
import json
import os
import urllib3

# Disable insecure request warnings for development
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Default to the production Render server for playtesters
# We now force USE_REMOTE to True so that built apps connect to Render automatically
USE_REMOTE = os.environ.get("RELMBAG_REMOTE", "true").lower() == "true"
SERVER_URL = "https://relmbag-server.onrender.com" if USE_REMOTE else "http://localhost:5050"

def safe_request(method: str, endpoint: str, **kwargs) -> requests.Response:
    """
    Makes a request to the server with a timeout and handles exceptions.
    """
    url = f"{SERVER_URL}/{endpoint}"
    try:
        # Use SSL verification for remote server, disable for local if needed
        # Increased timeout to 120s for Render spin-up/slow response
        verify_ssl = USE_REMOTE
        response = requests.request(method, url, timeout=120, verify=verify_ssl, **kwargs)
        print(f"[DEBUG] {method.upper()} {url} - Status: {response.status_code}")
        # We don't call raise_for_status() here anymore because we want to handle
        # 4xx errors gracefully in the application logic by reading the response JSON.
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
