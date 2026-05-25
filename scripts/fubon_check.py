#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys


def import_check() -> int:
    from fubon_neo.sdk import FubonSDK

    print("Fubon Neo SDK import OK")
    print(f"FubonSDK class: {FubonSDK}")
    return 0


def login_check() -> int:
    from fubon_neo.sdk import FubonSDK

    person_id = os.getenv("FUBON_PERSON_ID")
    api_key = os.getenv("FUBON_API_KEY")
    api_secret = os.getenv("FUBON_API_SECRET")
    password = os.getenv("FUBON_PASSWORD")
    cert_path = os.getenv("FUBON_CERT_PATH")
    cert_password = os.getenv("FUBON_CERT_PASSWORD")

    sdk = FubonSDK()
    if person_id and api_key and api_secret:
        accounts = sdk.apikey_login(person_id, api_key, api_secret)
    elif person_id and password and cert_path and cert_password:
        accounts = sdk.login(person_id, password, cert_path, cert_password)
    else:
        print(
            "Missing login environment variables. Set API key variables or certificate variables first.",
            file=sys.stderr,
        )
        return 2

    print("Fubon Neo SDK login OK")
    print(accounts)
    sdk.logout()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Fubon Neo SDK installation/login.")
    parser.add_argument("--login", action="store_true", help="Attempt login using environment variables.")
    args = parser.parse_args()

    if args.login:
        return login_check()
    return import_check()


if __name__ == "__main__":
    raise SystemExit(main())
