import os
import stat
from getpass import getpass

ENV_FILE = ".env"

CREDENTIALS = [
    ("DHAN_CLIENT_ID", "Dhan Client ID", False),
    ("DHAN_API_KEY", "Dhan API Key", True),
    ("DHAN_API_SECRET", "Dhan API Secret", True),
    ("DHAN_PIN", "Dhan Trading PIN", True),
    ("DHAN_MOBILE_NUMBER", "Registered Mobile Number", False),
    ("DHAN_TOTP_SEED", "TOTP Seed (for 2FA)", True),
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

    with open(ENV_FILE, "w") as f:
        for key, _, _ in CREDENTIALS:
            f.write(f"{key}={values[key]}\n")

    os.chmod(ENV_FILE, stat.S_IRUSR | stat.S_IWUSR)
    print(f"\n{ENV_FILE} created with restricted permissions (600).")


if __name__ == "__main__":
    main()
