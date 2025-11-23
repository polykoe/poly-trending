import requests

slug = "russia-x-ukraine-ceasefire-in-2025"
gamma_api_url = "https://gamma-api.polymarket.com"

# Method 1: Query params (WORKING)
r1 = requests.get(f"{gamma_api_url}/events", params={"slug": slug})
print("Query params:", r1.status_code, type(r1.json()))

# Method 2: Path (YOUR CURRENT CODE)
r2 = requests.get(f"{gamma_api_url}/events/slug/{slug}")
print("Path-based:", r2.status_code, type(r2.json()))