import getpass
import subprocess
import sys

print("==========================================================")
print(" Secure GMAIL_REFRESH_TOKEN Updater for Railway (production)")
print("==========================================================")
print("Input will be hidden while typing/pasting (characters will not display on screen).")
token = getpass.getpass("Paste your Gmail API Refresh Token here: ").strip().strip('"\'')

if not token:
    print("Error: No token entered. Operation cancelled.")
    sys.exit(1)

print("\nUpdating Railway environment variable GMAIL_REFRESH_TOKEN...")
proc = subprocess.run(
    [
        r".\scripts\railway_bin\railway.exe",
        "variable",
        "set",
        f"GMAIL_REFRESH_TOKEN={token}",
        "--service",
        "DailyExpenseTracker",
        "-e",
        "production"
    ],
    capture_output=True,
    text=True
)

if proc.returncode == 0:
    print("\n[SUCCESS] Variable GMAIL_REFRESH_TOKEN successfully updated on Railway!")
    print("Railway is deploying the update with the new Gmail API token.")
else:
    print("\n[ERROR] Failed to update variable on Railway:")
    print(proc.stderr)
    sys.exit(proc.returncode)
