import os
import httpx
from dotenv import load_dotenv

# Load credentials from .env
load_dotenv()

base = os.getenv("PAYPAL_BASE_URL")
client_id = os.getenv("PAYPAL_CLIENT_ID")
client_secret = os.getenv("PAYPAL_CLIENT_SECRET")

# Step 1: Authenticate with PayPal Sandbox
auth = httpx.post(
    f"{base}/v1/oauth2/token",
    auth=(client_id, client_secret),
    data={"grant_type": "client_credentials"},
    timeout=30,
)

print("Authentication:", auth.status_code)

if auth.status_code != 200:
    print("Authentication failed. Check your credentials.")
    raise SystemExit(1)

token = auth.json()["access_token"]

# Step 2: Test access to PayPal disputes
response = httpx.get(
    f"{base}/v1/customer/disputes",
    headers={"Authorization": f"Bearer {token}"},
    timeout=30,
)

print("Disputes API:", response.status_code)

if response.status_code == 200:
    disputes = response.json().get("items", [])
    print("Disputes found:", len(disputes))
    print("VERDICT connected successfully!")
else:
    print("Disputes API access failed.")
    print("Provider response body withheld from logs.")
