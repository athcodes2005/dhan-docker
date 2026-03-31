import os
import stat
import time
from getpass import getpass

import pyotp

ENV_FILE = ".env"

CREDENTIALS = [
    ("DHAN_CLIENT_ID", "Dhan Client ID", False),
    ("DHAN_API_KEY", "Dhan API Key", True),
    ("DHAN_API_SECRET", "Dhan API Secret", True),
    ("DHAN_PIN", "Dhan Trading PIN", True),
    ("DHAN_MOBILE_NUMBER", "Registered Mobile Number", False),
    ("DHAN_TOTP_SEED", "TOTP Seed (for 2FA)", True),
    ("ADMIN_PASSWORD", "Dashboard Admin Password", True),
    ("GUEST_PASSWORD", "Dashboard Guest Password", True),
    ("STATIC_IP", "Server Static IP (for order execution)", False),
]


def main():
    if os.path.exists(ENV_FILE):
        overwrite = input(f"{ENV_FILE} already exists. Overwrite? (y/N): ").strip().lower()
        if overwrite != "y":
            print("Aborted.")
            return

    print("Enter your Dhan credentials:\n")

    values = {}
    for key, label, secret in CREDENTIALS:
        prompt = f"  {label} ({key}): "
        value = getpass(prompt) if secret else input(prompt)
        values[key] = value.strip()

        if key == "DHAN_TOTP_SEED" and values[key]:
            totp = pyotp.TOTP(values[key].replace(" ", ""))
            print("\n  TOTP codes (refreshes automatically, press Ctrl+C when verified):\n")
            try:
                last_code = None
                while True:
                    code = totp.now()
                    remaining = totp.interval - (int(time.time()) % totp.interval)
                    if code != last_code:
                        print(f"\r  -> TOTP: {code}  (expires in {remaining:2d}s)  ", end="", flush=True)
                        last_code = code
                    else:
                        print(f"\r  -> TOTP: {code}  (expires in {remaining:2d}s)  ", end="", flush=True)
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n\n  TOTP verified. Saving credentials...\n")

    with open(ENV_FILE, "w") as f:
        for key, _, _ in CREDENTIALS:
            f.write(f"{key}={values[key]}\n")

    os.chmod(ENV_FILE, stat.S_IRUSR | stat.S_IWUSR)
    print(f"{ENV_FILE} created with restricted permissions (600).")


if __name__ == "__main__":
    main()
