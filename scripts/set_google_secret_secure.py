import getpass
import subprocess
import sys

print("==========================================================")
print(" Secure GOOGLE_CLIENT_SECRET Updater for Railway (production)")
print("==========================================================")
print("Input will be hidden while typing/pasting (characters will not display on screen).")
secret = getpass.getpass("Paste your Google Client Secret here: ").strip().strip('"\'')

if not secret:
    print("Error: No secret entered. Operation cancelled.")
    sys.exit(1)

if not secret.startswith("GOCSPX-"):
    print("\n[WARNING] Standard Google Web OAuth client secrets typically begin with 'GOCSPX-'.")
    ans = input("Proceed anyway? (y/N): ").strip().lower()
    if ans != 'y':
        print("Cancelled.")
        sys.exit(1)

print("\nUpdating Railway environment variable...")
proc = subprocess.run(
    [
        r".\scripts\railway_bin\railway.exe",
        "variable",
        "set",
        f"GOOGLE_CLIENT_SECRET={secret}",
        "--service",
        "DailyExpenseTracker",
        "-e",
        "production"
    ],
    capture_output=True,
    text=True
)

if proc.returncode == 0:
    print("\n[SUCCESS] Variable GOOGLE_CLIENT_SECRET successfully updated on Railway!")
    print("Railway is deploying the update with the new secret.")
else:
    print("\n[ERROR] Failed to update variable on Railway:")
    print(proc.stderr)
    sys.exit(proc.returncode)
