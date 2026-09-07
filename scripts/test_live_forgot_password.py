import urllib.request
import urllib.parse
import http.cookiejar
import re
import sys
import ssl

BASE_URL = "https://dailyexpensetracker-production-bf76.up.railway.app"

cj = http.cookiejar.CookieJar()
ctx = ssl.create_default_context()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj), urllib.request.HTTPSHandler(context=ctx))

def test_live_forgot_password():
    print("Testing live forgot-password route on:", BASE_URL)
    
    # 1. GET /forgot-password to get CSRF token
    req = urllib.request.Request(f"{BASE_URL}/forgot-password", headers={'User-Agent': 'Mozilla/5.0'})
    resp = opener.open(req)
    html = resp.read().decode('utf-8')
    assert resp.getcode() == 200
    
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    assert match, "CSRF token not found"
    csrf_token = match.group(1)
    print("Obtained CSRF token from live production.")

    target_email = sys.argv[1] if len(sys.argv) > 1 else 'test.expenseflow.verify@gmail.com'
    print(f"Testing forgot-password dispatch for: {target_email}")
    data = urllib.parse.urlencode({
        'email': target_email,
        'csrf_token': csrf_token
    }).encode('utf-8')
    
    req = urllib.request.Request(f"{BASE_URL}/forgot-password", data=data, headers={'User-Agent': 'Mozilla/5.0'})
    resp = opener.open(req)
    final_url = resp.geturl()
    body = resp.read().decode('utf-8')

    print("Response URL:", final_url)
    print("Response status:", resp.getcode())
    
    # Check that Sandbox Restriction is NOT present
    if "Resend Sandbox Restriction" in body:
        print("[FAIL] Red Resend Sandbox Restriction warning appeared!")
        print("Snippet:", body[body.find("Resend Sandbox Restriction"):body.find("Resend Sandbox Restriction")+200])
        return False

    print("Checking if sandbox restriction is absent... PASSED (No sandbox warning!)")
    
    # Check if redirect to verify-reset-otp occurred or success message shown
    if "/verify-reset-otp" in final_url:
        print("[PASS] Successfully redirected to /verify-reset-otp!")
    else:
        print("Page text snippet:", body[:500])

    return True

if __name__ == "__main__":
    test_live_forgot_password()
