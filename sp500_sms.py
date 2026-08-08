"""
Daily S&P 500 SMS updater using Twilio.

WHAT THIS DOES
--------------
Fetches the latest S&P 500 (^GSPC) price + daily change from Yahoo Finance
(no API key needed) and sends it as a plain SMS text via Twilio.

SETUP (one-time)
-----------------
1. Create a free Twilio account: https://www.twilio.com/try-twilio
   Trial accounts get free credit (~$15), enough for hundreds of texts.

2. Get a Twilio phone number:
   - Twilio Console > Phone Numbers > Buy a number (a trial account can
     claim one for free using trial credit).
   - Copy the number in E.164 format, e.g. +18445551234.

3. Verify YOUR phone number (required on trial accounts):
   - Twilio Console > Phone Numbers > Verified Caller IDs > Add a new one.
   - Trial accounts can only send SMS to verified numbers. Once you
     upgrade the account (add a few dollars), this restriction goes away.

4. Install dependencies:
     pip install twilio yfinance --break-system-packages

5. Set these environment variables (Account SID / Auth Token are on the
   Twilio Console dashboard):
     export TWILIO_ACCOUNT_SID="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
     export TWILIO_AUTH_TOKEN="your_auth_token"
     export TWILIO_SMS_FROM="+18445551234"     # your Twilio number
     export MY_SMS_TO="+1XXXXXXXXXX"           # YOUR phone, E.164 format

6. Run it manually to test:
     python3 sp500_sms.py

7. Automate it daily — see the accompanying GitHub Actions workflow
   (daily-sp500-sms.yml) to run this in the cloud for free, or use cron /
   Task Scheduler to run it locally.

NOTE ON COST
------------
SMS in the US is roughly $0.0079/message via Twilio. At one text per
weekday, trial credit alone covers this for years. No WhatsApp sandbox
join-code step is needed for SMS — it works out of the box once your
Twilio number and verified recipient are set up.
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

    arrow_word = "UP" if change >= 0 else "DOWN"

    message = (
        f"S&P 500 Update - {date_str}\n"
        f"Close: {latest_close:,.2f}\n"
        f"{arrow_word} {change:+,.2f} ({pct_change:+.2f}%)"
    )
    return message


def send_sms(body: str):
    from twilio.rest import Client

    account_sid = os.environ["TWILIO_ACCOUNT_SID"]
    auth_token = os.environ["TWILIO_AUTH_TOKEN"]
    from_number = os.environ["TWILIO_SMS_FROM"]
    to_number = os.environ["MY_SMS_TO"]

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

    required_vars = ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_SMS_FROM", "MY_SMS_TO"]
    missing = [v for v in required_vars if not os.environ.get(v)]
    if missing:
        print(f"\n[Not sent] Missing environment variables: {', '.join(missing)}")
        print("Set them and re-run to actually send the text.")
        return

    try:
        sid = send_sms(summary)
        print(f"\nSent! Twilio message SID: {sid}")
    except Exception as e:
        print(f"[{datetime.now()}] Failed to send SMS: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
