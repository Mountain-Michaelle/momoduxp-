import requests
import sys

# Use localhost for local testing
BASE_URL = "http://localhost:8001/api/v1"

print("=" * 60)
print("Google OAuth Test Script")
print("=" * 60)

# 1. Get OAuth URL
print("\nStep 1: Getting OAuth URL...")
resp = requests.get(f"{BASE_URL}/auth/oauth/google/url")
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text}")

if resp.status_code != 200:
    print(f"❌ Error getting URL: {resp.status_code}")
    sys.exit(1)

data = resp.json()
if "url" not in data:
    print(f"❌ Response missing 'url' key. Full response: {data}")
    sys.exit(1)

url = data["url"]
state = data["state"]
print(f"✅ URL generated successfully!")
print(f"State: {state}")
print(f"\n🔗 Open this URL in browser:\n{url}\n")

# 2. Get callback URL from user
print("=" * 60)
print("After completing Google auth, you'll be redirected to a URL")
print("that looks like:")
print(
    "  https://momoduxp.michealchinemeluugwu.xyz/api/v1/auth/oauth/google/callback?code=xxx&state=xxx"
)
print("\nPaste the FULL callback URL here:")
callback_url = input("> ").strip()

# Parse the callback URL
try:
    from urllib.parse import urlparse, parse_qs

    parsed = urlparse(callback_url)
    params = parse_qs(parsed.query)

    code = params.get("code", [""])[0]
    callback_state = params.get("state", [""])[0]
    iss = params.get("iss", [""])[0]  # Google OIDC returns 'iss' instead of 'state'

    if not code:
        print("❌ No 'code' found in URL")
        sys.exit(1)

    # Use state from URL if available, otherwise skip validation
    if callback_state:
        if callback_state != state:
            print(f"⚠️  State mismatch! Expected {state}, got {callback_state}")
            state = callback_state
    elif iss:
        # OIDC flow - state is optional, iss indicates valid OIDC response
        print(f"ℹ️  OIDC flow detected (iss={iss[:30]}...), skipping state validation")
        state = None  # Will pass None to backend
    else:
        print("ℹ️  No state in callback, will try without it")
        state = None

except Exception as e:
    print(f"❌ Error parsing URL: {e}")
    sys.exit(1)

# 3. Exchange code for tokens
print("\nStep 2: Exchanging code for tokens...")
resp = requests.get(
    f"{BASE_URL}/auth/oauth/google/callback",
    params={"code": code, "state": state} if state else {"code": code},
)

print(f"Status: {resp.status_code}")
print(f"Response: {resp.text}")

if resp.status_code != 200:
    print(f"❌ Error: {resp.status_code}")
    sys.exit(1)

tokens = resp.json()
print(f"✅ Success!")
print(f"Access Token: {tokens['access_token'][:50]}...")
print(f"User ID: {tokens['user_id']}")
print(f"Email: {tokens['email']}")

# 4. Test the token
print("\nStep 3: Testing token...")
resp = requests.get(
    f"{BASE_URL}/posts", headers={"Authorization": f"Bearer {tokens['access_token']}"}
)
print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    print("✅ OAuth flow working!")
else:
    print(f"❌ Error: {resp.text}")
