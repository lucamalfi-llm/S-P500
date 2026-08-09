"""
Daily S&P 500 + Fed Rate text updater - FREE VERSION (email-to-SMS gateway).

WHAT THIS DOES
--------------
Fetches:
  1. The latest S&P 500 (^GSPC) price + daily change, from Yahoo Finance.
  2. The latest Effective Federal Funds Rate, from FRED (Federal Reserve
     Economic Data - the Fed's own free public database).
Then sends both as a single text message via Verizon's email-to-SMS
gateway. No Twilio, no fees.

NEW SETUP STEP: FRED API KEY (free, instant)
----------------------------------------------
1. Go to https://fred.stlouisfed.org/docs/api/api_key.html
2. Click "Request API Key" - sign up for a free FRED account if you don't
   have one, then request the key. It's issued instantly, no approval
   wait, no cost.
3. Copy the key (a long string of letters/numbers).

ALL SETUP (full list, including steps from before)
-----------------------------------------------------
1. Gmail App Password - see earlier version of this script for details
   if you haven't already set this up.
2. FRED API key - see above.
3. Install dependencies:
     pip install yfinance requests --break-system-packages
4. Set environment variables:
     export GMAIL_ADDRESS="youraccount@gmail.com"
     export GMAIL_APP_PASSWORD="the16charapppassword"
     export PHONE_NUMBER="1234567890"
     export CARRIER_GATEWAY="vtext.com"
     export FRED_API_KEY="your_fred_api_key"
5. Run manually to test:
     python3 sp500_email_sms.py

NOTE ON THE FED RATE NUMBER
-----------------------------
This uses FRED series "DFF" (Effective Federal Funds Rate), which is the
actual daily rate depository institutions trade at - not the FOMC's
official target *range* you often hear quoted in the news (e.g.
"4.25%-4.50%"). DFF is a single number that typically sits within that
target range. It only updates on business days and reflects the most
recent day the Fed has published.
"""

import os
import sys
from datetime import datetime

import requests


CARRIER_GATEWAYS = {
    "verizon": "vtext.com",
    "att": "txt.att.net",
    "tmobile": "tmomail.net",
    "sprint": "messaging.sprintpcs.com",
    "boost": "sms.myboostmobile.com",
    "cricket": "sms.cricketwireless.net",
    "metropcs": "mymetropcs.com",
    "uscellular": "email.uscc.net",
    "googlefi": "msg.fi.google.com",
    "visible": "vtext.com",
}


def get_sp500_line():
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

    header = f"S&P 500 Update - {date_str}"
    body = f"Close: {latest_close:,.2f}\n{arrow_word} {change:+,.2f} ({pct_change:+.2f}%)"
    return header, body


def get_fed_rate_line():
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        return None  # skip gracefully if not configured

    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": "DFF",  # Effective Federal Funds Rate
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 1,
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    obs = data["observations"][0]
    rate = obs["value"]
    obs_date = obs["date"]

    return f"Fed Funds Rate: {rate}% (as of {obs_date})"


def build_message():
    sp500_header, sp500_body = get_sp500_line()
    lines = [sp500_header, sp500_body]

    try:
        fed_line = get_fed_rate_line()
        if fed_line:
            lines.append(fed_line)
    except Exception as e:
        # Don't let a Fed data hiccup block the S&P 500 text from sending.
        print(f"[warning] Could not fetch Fed rate: {e}", file=sys.stderr)

    return "\n".join(lines)


def send_email_sms(body: str):
    import smtplib
    from email.mime.text import MIMEText

    gmail_address = os.environ["GMAIL_ADDRESS"]
    gmail_app_password = os.environ["GMAIL_APP_PASSWORD"]
    phone_number = os.environ["PHONE_NUMBER"]
    carrier_gateway = os.environ["CARRIER_GATEWAY"]

    to_address = f"{phone_number}@{carrier_gateway}"

    msg = MIMEText(body)
    msg["Subject"] = ""
    msg["From"] = gmail_address
    msg["To"] = to_address

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(gmail_address, gmail_app_password)
        server.sendmail(gmail_address, [to_address], msg.as_string())


def main():
    try:
        message = build_message()
    except Exception as e:
        print(f"[{datetime.now()}] Failed to build message: {e}", file=sys.stderr)
        sys.exit(1)

    print("Message to send:\n" + message)

    required_vars = ["GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "PHONE_NUMBER", "CARRIER_GATEWAY"]
    missing = [v for v in required_vars if not os.environ.get(v)]
    if missing:
        print(f"\n[Not sent] Missing environment variables: {', '.join(missing)}")
        return

    try:
        send_email_sms(message)
        print("\nSent!")
    except Exception as e:
        print(f"[{datetime.now()}] Failed to send text: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
