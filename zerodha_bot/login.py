"""Zerodha needs a fresh login every morning. python login.py  -> prints the login URL; after you log in, Kite redirects to a URL that contains
request_token=XXXX. Paste ONLY that token here (never into a chat). The access token is written to .access_token (git-ignored) and printed as an export line."""
import os, sys
from kiteconnect import KiteConnect

key, secret = os.environ.get("KITE_API_KEY"), os.environ.get("KITE_API_SECRET")
if not key or not secret: sys.exit("Set KITE_API_KEY and KITE_API_SECRET in your shell first (see .env.example).")
kite = KiteConnect(api_key=key)
print("1) Open this URL and log in:\n  ", kite.login_url())
tok = input("2) Paste the request_token from the redirected URL: ").strip()
data = kite.generate_session(tok, api_secret=secret)
open(".access_token", "w").write(data["access_token"])
print("\nDone. Run this in your shell:\n  export KITE_ACCESS_TOKEN=$(cat .access_token)")
