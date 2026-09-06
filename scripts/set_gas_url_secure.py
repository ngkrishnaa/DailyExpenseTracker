import subprocess
import sys

print("==========================================================")
print(" Set GAS_WEBAPP_URL on Railway (Production)")
print("==========================================================")
url = input("Paste your Google Apps Script Web App URL here: ").strip().strip('"\'')

if not url:
    print("Error: No URL entered. Operation cancelled.")
    sys.exit(1)

if not url.startswith("https://script.google.com/macros/s/"):
    print("[WARNING] Expected URL starting with 'https://script.google.com/macros/s/'.")
    ans = input("Proceed anyway? (y/N): ").strip().lower()
    if ans != 'y':
        print("Cancelled.")
        sys.exit(1)

print("\nSetting Railway environment variable GAS_WEBAPP_URL...")
proc = subprocess.run(
    [
        r".\scripts\railway_bin\railway.exe",
        "variable",
        "set",
        f"GAS_WEBAPP_URL={url}",
        "--service",
        "DailyExpenseTracker",
        "-e",
        "production"
    ],
    capture_output=True,
    text=True
)

if proc.returncode == 0:
    print("\n[SUCCESS] Variable GAS_WEBAPP_URL successfully updated on Railway!")
    print("Railway is deploying the update.")
else:
    print("\n[ERROR] Failed to update variable on Railway:")
    print(proc.stderr)
    sys.exit(proc.returncode)
