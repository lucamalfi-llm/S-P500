"""
Daily S&P 500 WhatsApp updater using Twilio.

WHAT THIS DOES
--------------
Fetches the latest S&P 500 (^GSPC) price + daily change from Yahoo Finance
(no API key needed) and sends it as a WhatsApp message via Twilio.

SETUP (one-time)
-----------------
1. Create a free Twilio account: https://www.twilio.com/try-twilio

2. Activate the Twilio WhatsApp Sandbox (fastest way to get started):
   - Go to: Twilio Console > Messaging > Try it out > Send a WhatsApp message
   - You'll get a Twilio WhatsApp number (usually +1 415 523 8886) and a
     join code like "join <two-words>".
   - From YOUR phone's WhatsApp, send that join code to that Twilio number.
     This links your personal WhatsApp number to the sandbox so Twilio is
     allowed to message you.
   - Note: sandbox sessions expire after 72 hours of inactivity — you'd
     need to re-send the join code periodically. For a permanent bot you
     eventually apply for a real WhatsApp Business sender (see bottom).

3. Install dependencies:
     pip install twilio yfinance --break-system-packages

4. Set these environment variables (get Account SID / Auth Token from the
   Twilio Console dashboard):
     export TWILIO_ACCOUNT_SID="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
     export TWILIO_AUTH_TOKEN="your_auth_token"
     export TWILIO_WHATSAPP_FROM="whatsapp:+14155238886"   # Twilio sandbox number
     export MY_WHATSAPP_TO="whatsapp:+1XXXXXXXXXX"         # YOUR number, E.164 format

5. Run it manually to test:
     python3 sp500_whatsapp.py

6. Automate it daily (pick one):
   - Cron (Mac/Linux), e.g. run at 4:30pm ET on weekdays:
       30 16 * * 1-5 /usr/bin/python3 /path/to/sp500_whatsapp.py
   - Windows Task Scheduler: create a daily trigger that runs
       python.exe C:\path\to\sp500_whatsapp.py
   - Or a free cloud cron service (e.g. a scheduled GitHub Action, or a
     small always-on server / Render.com / PythonAnywhere scheduled task)
     if you don't want to rely on your own machine being on.
"""

import os
import sys
from datetime import datetime

def get_sp500_summary():
    import yfinance as yf

    ticker = yf.Ticker("^GSPC")
    hist = ticker.history(period="5d")

    if hist.empty or len(hist) < 2:
        raise RuntimeError("Could not retrieve enough S&P 500 price history.")

    latest_close = hist["Close"].iloc[-1]
    prev_close = hist["Close"].iloc[-2]
    change = latest_close - prev_close
    pct_change = (change / prev_close) * 100
    date_str = hist.index[-1].strftime("%b %d, %Y")

    arrow = "\U0001F53C" if change >= 0 else "\U0001F53D"  # green/red-ish up/down arrows

    message = (
        f"\U0001F4C8 S&P 500 Update — {date_str}\n"
        f"Close: {latest_close:,.2f}\n"
        f"Change: {arrow} {change:+,.2f} ({pct_change:+.2f}%)"
    )
    return message


def send_whatsapp_message(body: str):
    from twilio.rest import Client

    account_sid = os.environ["TWILIO_ACCOUNT_SID"]
    auth_token = os.environ["TWILIO_AUTH_TOKEN"]
    from_number = os.environ["TWILIO_WHATSAPP_FROM"]
    to_number = os.environ["MY_WHATSAPP_TO"]

    client = Client(account_sid, auth_token)

    msg = client.messages.create(
        body=body,
        from_=from_number,
        to=to_number,
    )
    return msg.sid


def main():
    try:
        summary = get_sp500_summary()
    except Exception as e:
        print(f"[{datetime.now()}] Failed to fetch S&P 500 data: {e}", file=sys.stderr)
        sys.exit(1)

    print("Message to send:\n" + summary)

    # Only attempt to send if Twilio env vars are configured.
    required_vars = ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM", "MY_WHATSAPP_TO"]
    missing = [v for v in required_vars if not os.environ.get(v)]
    if missing:
        print(f"\n[Not sent] Missing environment variables: {', '.join(missing)}")
        print("Set them and re-run to actually send via WhatsApp.")
        return

    try:
        sid = send_whatsapp_message(summary)
        print(f"\nSent! Twilio message SID: {sid}")
    except Exception as e:
        print(f"[{datetime.now()}] Failed to send WhatsApp message: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
