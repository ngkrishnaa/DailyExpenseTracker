import urllib.request
import urllib.parse
import http.cookiejar
import re
import sys
import ssl

BASE_URL = "https://dailyexpensetracker-production-bf76.up.railway.app"

# Setup cookie jar and opener
cj = http.cookiejar.CookieJar()
ctx = ssl.create_default_context()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj), urllib.request.HTTPSHandler(context=ctx))

def get(url, allow_redirects=True):
    class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
        def http_error_302(self, req, fp, code, msg, headers):
            return fp
        http_error_301 = http_error_303 = http_error_307 = http_error_302

    if not allow_redirects:
        op = urllib.request.build_opener(NoRedirectHandler, urllib.request.HTTPCookieProcessor(cj), urllib.request.HTTPSHandler(context=ctx))
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            resp = op.open(req, timeout=15)
            return resp.getcode(), resp.read().decode('utf-8', errors='replace'), resp.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode('utf-8', errors='replace'), e.headers
    else:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            resp = opener.open(req, timeout=15)
            return resp.getcode(), resp.read().decode('utf-8', errors='replace'), resp.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode('utf-8', errors='replace'), e.headers

def post(url, data):
    encoded_data = urllib.parse.urlencode(data).encode('utf-8')
    req = urllib.request.Request(url, data=encoded_data, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        resp = opener.open(req, timeout=15)
        return resp.getcode(), resp.read().decode('utf-8', errors='replace'), resp.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', errors='replace'), e.headers

def test_production():
    print(f"Testing live production site at: {BASE_URL}")

    # 1. DB Health Check
    code, text, headers = get(f"{BASE_URL}/test-db")
    print(f"[/test-db] Status: {code}, Body: {text.strip()}")
    assert code == 200, f"Expected 200, got {code}"
    assert "Database connected successfully!" in text

    # 2. Home Page
    code, text, headers = get(f"{BASE_URL}/")
    print(f"[/] Status: {code}, Title in HTML: {'Daily Expense Tracker' in text or 'ExpenseFlow' in text}")
    assert code == 200

    # 3. Login Page
    code, text, headers = get(f"{BASE_URL}/login")
    print(f"[/login] Status: {code}")
    assert code == 200
    assert 'name="email"' in text
    assert 'name="password"' in text
    assert 'csrf_token' in text
    assert 'Continue with Google' in text or 'google' in text.lower()
    assert 'Forgot Password?' in text or 'Forgot' in text

    # 4. Register Page
    code, text, headers = get(f"{BASE_URL}/register")
    print(f"[/register] Status: {code}")
    assert code == 200
    assert 'name="name"' in text
    assert 'name="email"' in text
    assert 'name="password"' in text
    assert 'name="confirm_password"' in text
    assert 'csrf_token' in text

    # 5. Forgot Password Page
    code, text, headers = get(f"{BASE_URL}/forgot-password")
    print(f"[/forgot-password] Status: {code}")
    assert code == 200
    assert 'name="email"' in text
    assert 'csrf_token' in text

    # 6. Protected Routes Redirect when unauthenticated
    for route in ['/dashboard', '/expenses', '/budget', '/reports', '/profile', '/set-password']:
        code, text, headers = get(f"{BASE_URL}{route}", allow_redirects=False)
        loc = headers.get('Location', '')
        print(f"[{route}] Unauthenticated Status: {code} (Location: {loc})")
        assert code in (302, 303, 307, 308), f"Expected redirect for {route}, got {code}"
        assert '/login' in loc

    # 7. Non-existent route 404 sanitization
    code, text, headers = get(f"{BASE_URL}/nonexistent-route-for-testing-404")
    print(f"[/404] Status: {code}")
    assert code == 404
    assert 'Traceback' not in text
    assert 'File "' not in text
    assert 'MYSQL_' not in text

    # 8. POST /login with invalid credentials gives user friendly error
    code, text, headers = get(f"{BASE_URL}/login")
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', text)
    if match:
        csrf_token = match.group(1)
        code, text, headers = post(f"{BASE_URL}/login", {
            'email': 'nonexistent_test_user@example.com',
            'password': 'WrongPassword123!',
            'csrf_token': csrf_token
        })
        print(f"[POST /login (invalid)] Status: {code}")
        assert 'Traceback' not in text
        assert 'SQL' not in text
        assert ('Invalid email or password' in text or 
                'Please check your credentials' in text or 
                'Invalid' in text)

    print("\nALL PRODUCTION SMOKE TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_production()
