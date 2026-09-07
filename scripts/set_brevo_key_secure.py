import getpass
import subprocess
import sys

print("==========================================================")
print(" Set BREVO_API_KEY on Railway (Production)")
print("==========================================================")
print("Input will be hidden while typing/pasting.")
key = getpass.getpass("Paste your Brevo API Key here: ").strip().strip('"\'')

if not key:
    print("Error: No key entered. Operation cancelled.")
    sys.exit(1)

print("\nSetting Railway environment variable BREVO_API_KEY...")
proc = subprocess.run(
    [
        r".\scripts\railway_bin\railway.exe",
        "variable",
        "set",
        f"BREVO_API_KEY={key}",
        "--service",
        "DailyExpenseTracker",
        "-e",
        "production"
    ],
    capture_output=True,
    text=True
)

if proc.returncode == 0:
    print("\n[SUCCESS] Variable BREVO_API_KEY successfully updated on Railway!")
    print("Railway is deploying the update with Brevo active.")
else:
    print("\n[ERROR] Failed to update variable on Railway:")
    print(proc.stderr)
    sys.exit(proc.returncode)
