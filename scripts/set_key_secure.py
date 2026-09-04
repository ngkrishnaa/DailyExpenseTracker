import getpass
import subprocess
import sys

print("==========================================================")
print(" Secure RESEND_API_KEY Updater for Railway (production)")
print("==========================================================")
print("Input will be hidden while typing/pasting.")
key = getpass.getpass("Paste your complete Resend API Key here: ").strip().strip('"\'')

if not key:
    print("Error: No key entered. Operation cancelled.")
    sys.exit(1)

if len(key) < 25 or not key.startswith("re_") or key.endswith(".."):
    print(f"\n[WARNING] The entered key is {len(key)} characters.")
    print("A full Resend API key typically starts with 're_' and is ~36 characters long.")
    ans = input("Proceed anyway? (y/N): ").strip().lower()
    if ans != 'y':
        print("Cancelled.")
        sys.exit(1)

print("\nUpdating Railway environment variable...")
proc = subprocess.run(
    [
        r".\scripts\railway_bin\railway.exe",
        "variables",
        "--set",
        f"RESEND_API_KEY={key}",
        "-s",
        "DailyExpenseTracker",
        "-e",
        "production"
    ],
    capture_output=True,
    text=True
)

if proc.returncode == 0:
    print("\n[SUCCESS] Variable RESEND_API_KEY successfully updated on Railway!")
    print("Railway has automatically triggered a new deployment.")
else:
    print("\n[ERROR] Failed to update variable on Railway:")
    print(proc.stderr)
    sys.exit(proc.returncode)
