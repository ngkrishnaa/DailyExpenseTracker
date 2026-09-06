import urllib.request
import urllib.parse
import http.cookiejar
import re
import ssl
import time

BASE_URL = "https://dailyexpensetracker-production-bf76.up.railway.app"

cj = http.cookiejar.CookieJar()
ctx = ssl.create_default_context()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj), urllib.request.HTTPSHandler(context=ctx))

def test_live_registration():
    print("Testing live registration route on:", BASE_URL)
    
    # 1. GET /register
    req = urllib.request.Request(f"{BASE_URL}/register", headers={'User-Agent': 'Mozilla/5.0'})
    resp = opener.open(req)
    html = resp.read().decode('utf-8')
    assert resp.getcode() == 200
    
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    assert match, "CSRF token not found"
    csrf_token = match.group(1)

    # 2. POST /register with test user
    test_email = f"prod_test_{int(time.time())}@example.com"
    data = urllib.parse.urlencode({
        'name': 'Production Tester',
        'email': test_email,
        'password': 'SecurePassword123!',
        'confirm_password': 'SecurePassword123!',
        'terms': 'on',
        'csrf_token': csrf_token
    }).encode('utf-8')

    req = urllib.request.Request(f"{BASE_URL}/register", data=data, headers={'User-Agent': 'Mozilla/5.0'})
    resp = opener.open(req)
    final_url = resp.geturl()
    body = resp.read().decode('utf-8')

    print("Registration Response URL:", final_url)
    print("Registration Response code:", resp.getcode())

    # Ensure NO Resend sandbox restriction appears
    assert "Resend Sandbox Restriction" not in body, "Sandbox restriction warning found!"
    print("Checked absence of Sandbox restriction: PASSED!")

    # Check for verification code screen
    if "verify_otp" in final_url or "Verification Code" in body or "verify" in body.lower():
        print("[PASS] Registration successfully moved to OTP verification screen!")
        return True
    else:
        print("[FAIL] Unexpected response:", body[:300])
        return False

if __name__ == "__main__":
    test_live_registration()
