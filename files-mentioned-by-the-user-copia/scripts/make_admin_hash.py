from __future__ import annotations

import base64
import getpass
import hashlib
import secrets


def main() -> None:
    password = getpass.getpass("Nuova password admin: ")
    confirm = getpass.getpass("Ripeti password admin: ")
    if not password or password != confirm:
        raise SystemExit("Password vuota o non coincidente.")
    rounds = 260_000
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii")
    digest_b64 = base64.urlsafe_b64encode(digest).decode("ascii")
    print(f"pbkdf2_sha256${rounds}${salt_b64}${digest_b64}")


if __name__ == "__main__":
    main()
