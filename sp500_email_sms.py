"""
Daily Market Update text - FREE VERSION (email-to-SMS gateway).

WHAT THIS DOES
--------------
Fetches and texts a daily market summary:
  1. S&P 500 (^GSPC) - price + daily change
  2. Nasdaq Composite (^IXIC) - price + daily change
  3. Dow Jones (^DJI) - price + daily change
  4. 10-Year Treasury Yield (^TNX)
  5. Fed Funds Rate (from FRED)
  6. Top 3 gaining and top 3 losing S&P 500 sectors (via sector ETFs)

All from free sources: Yahoo Finance (via yfinance) for market data, and
FRED (Federal Reserve's free API) for the Fed rate. Sent via Verizon's
free email-to-SMS gateway. No Twilio, no fees.

SETUP
-----
Same as before - see earlier comments/previous versions for full details
on Gmail App Password + FRED API key. Environment variables needed:
     export GMAIL_ADDRESS="youraccount@gmail.com"
     export GMAIL_APP_PASSWORD="the16charapppassword"
     export PHONE_NUMBER="1234567890"
     export CARRIER_GATEWAY="vtext.com"
     export FRED_API_KEY="your_fred_api_key"

Install: pip install yfinance requests --break-system-packages

NOTE ON SECTORS
---------------
S&P 500 sectors are tracked here using the 11 "Select Sector SPDR" ETFs
(the standard, widely-used proxy for each GICS sector - e.g. XLK for
Technology, XLF for Financials, etc.). Each one's daily % change is used
to rank sectors, since there's no free direct feed of "S&P sector index"
values from Yahoo Finance.

NOTE ON 10-YEAR YIELD
----------------------
Yahoo Finance's ^TNX quotes the 10-Year Treasury yield x10 (a historical
quirk - so a displayed value of "42.5" means 4.25%). This script divides
by 10 automatically before showing it.

A message this size (6 data points) may occasionally exceed the
traditional 160-character single-SMS limit - most carriers/phones handle
this fine as an auto-split "long SMS," but it's worth knowing in case
your phone shows it as two separate texts.
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

SECTOR_ETFS = {
    "XLK": "Technology",
    "XLF": "Financials",
    "XLV": "Health Care",
    "XLY": "Consumer Disc.",
    "XLP": "Consumer Staples",
    "XLE": "Energy",
    "XLI": "Industrials",
    "XLB": "Materials",
    "XLU": "Utilities",
    "XLRE": "Real Estate",
    "XLC": "Comm. Services",
}


def _pct_change(hist):
    if hist.empty or len(hist) < 2:
        raise RuntimeError("Not enough price history.")
    latest = hist["Close"].iloc[-1]
    prev = hist["Close"].iloc[-2]
    change = latest - prev
    pct = (change / prev) * 100
    return latest, change, pct


def get_index_line(ticker_symbol, label):
    import yfinance as yf

    hist = yf.Ticker(ticker_symbol).history(period="5d")
    latest, change, pct = _pct_change(hist)
    arrow_word = "UP" if change >= 0 else "DOWN"
    return f"{label}: {latest:,.2f} {arrow_word} {change:+,.2f} ({pct:+.2f}%)"


def get_treasury_yield_line():
    import yfinance as yf

    hist = yf.Ticker("^TNX").history(period="5d")
    if hist.empty:
        raise RuntimeError("Could not retrieve 10-year Treasury yield.")
    latest_raw = hist["Close"].iloc[-1]
    yield_pct = latest_raw / 10  # Yahoo quotes ^TNX as yield x10
    return f"10-Yr Treasury Yield: {yield_pct:.2f}%"


def get_fed_rate_line():
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        return None

    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": "DFF",
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 1,
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    obs = resp.json()["observations"][0]
    return f"Fed Funds Rate: {obs['value']}% (as of {obs['date']})"


def get_mortgage_rate_lines():
    """Returns average 30-year and 15-year fixed mortgage rates from
    Freddie Mac's survey via FRED. These update weekly (Thursdays), so
    the same value may repeat for several days between updates."""
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        return None

    url = "https://api.stlouisfed.org/fred/series/observations"
    lines = []
    for series_id, label in [("MORTGAGE30US", "30-Yr Mortgage"), ("MORTGAGE15US", "15-Yr Mortgage")]:
        params = {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 1,
        }
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        obs = resp.json()["observations"][0]
        lines.append(f"{label}: {obs['value']}% (as of {obs['date']})")

    return lines


def get_sector_lines():
    import yfinance as yf

    results = []
    for etf, name in SECTOR_ETFS.items():
        try:
            hist = yf.Ticker(etf).history(period="5d")
            _, _, pct = _pct_change(hist)
            results.append((name, pct))
        except Exception as e:
            print(f"[warning] Could not fetch sector {name} ({etf}): {e}", file=sys.stderr)

    if not results:
        return None

    results.sort(key=lambda x: x[1], reverse=True)
    top_gainers = results[:3]
    top_losers = results[-3:][::-1]  # worst first

    gainer_str = ", ".join(f"{name} {pct:+.1f}%" for name, pct in top_gainers)
    loser_str = ", ".join(f"{name} {pct:+.1f}%" for name, pct in top_losers)

    return f"Top Sectors: {gainer_str}\nBottom Sectors: {loser_str}"


def build_messages():
    """Returns a list of message strings - sent as separate texts, since
    Verizon's email-to-SMS gateway doesn't reliably auto-split long
    messages into multiple parts (it can silently drop the overflow)."""
    date_str = datetime.now().strftime("%b %d, %Y")

    # --- Message 1: S&P 500 + sector performance ---
    msg1_lines = [f"Market Update 1/2 - {date_str}"]
    msg1_lines.append(get_index_line("^GSPC", "S&P 500"))

    try:
        sector_lines = get_sector_lines()
        if sector_lines:
            msg1_lines.append(sector_lines)
    except Exception as e:
        print(f"[warning] Could not fetch sector data: {e}", file=sys.stderr)

    message1 = "\n".join(msg1_lines)

    # --- Message 2: Fed rate + mortgage rates ---
    msg2_lines = [f"Market Update 2/2 - {date_str}"]

    try:
        fed_line = get_fed_rate_line()
        if fed_line:
            msg2_lines.append(fed_line)
    except Exception as e:
        print(f"[warning] Could not fetch Fed rate: {e}", file=sys.stderr)

    try:
        mortgage_lines = get_mortgage_rate_lines()
        if mortgage_lines:
            msg2_lines.extend(mortgage_lines)
    except Exception as e:
        print(f"[warning] Could not fetch mortgage rates: {e}", file=sys.stderr)

    message2 = "\n".join(msg2_lines)

    return [message1, message2]


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
    import time

    try:
        messages = build_messages()
    except Exception as e:
        print(f"[{datetime.now()}] Failed to build messages: {e}", file=sys.stderr)
        sys.exit(1)

    for i, message in enumerate(messages, start=1):
        print(f"\nMessage {i} to send:\n{message}")

    required_vars = ["GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "PHONE_NUMBER", "CARRIER_GATEWAY"]
    missing = [v for v in required_vars if not os.environ.get(v)]
    if missing:
        print(f"\n[Not sent] Missing environment variables: {', '.join(missing)}")
        return

    for i, message in enumerate(messages, start=1):
        try:
            send_email_sms(message)
            print(f"\nSent message {i}!")
        except Exception as e:
            print(f"[{datetime.now()}] Failed to send message {i}: {e}", file=sys.stderr)
        if i < len(messages):
            time.sleep(10)  # small gap so carrier doesn't merge/drop them


if __name__ == "__main__":
    main()
