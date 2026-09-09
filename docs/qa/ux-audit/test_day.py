import urllib.request
import json
import uuid

base = "http://127.0.0.1:8000"

# Register
email = f"test_day_{uuid.uuid4().hex[:8]}@travix.ai"
req = urllib.request.Request(f"{base}/api/v1/auth/register", data=json.dumps({"email": email, "password": "Password123!", "full_name": "Test"}).encode(), headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read())
    token = data["data"]["access_token"]

# Create trip
req = urllib.request.Request(f"{base}/api/v1/trips", data=json.dumps({"title": "Test Trip", "departure_date": "2026-10-01", "return_date": "2026-10-04"}).encode(), headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read())
    trip_id = data["data"]["trip_id"]

# Add Day
req = urllib.request.Request(f"{base}/api/v1/trips/{trip_id}/itinerary/days", data=json.dumps({"day_number": 1, "title": "Day 1", "date": "2026-10-01"}).encode(), headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read())
    print("ADD DAY RESPONSE:")
    print(json.dumps(data, indent=2))
