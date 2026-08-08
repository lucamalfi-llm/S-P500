"""
Daily S&P 500 text updater - FREE VERSION (email-to-SMS gateway, no Twilio).

WHAT THIS DOES
--------------
Fetches the latest S&P 500 (^GSPC) price + daily change from Yahoo Finance,
then sends it as a text message by emailing Verizon's email-to-SMS gateway
(number@vtext.com). No Twilio account, no fees, no approval process.

HOW IT WORKS
------------
Verizon (and other US carriers) automatically convert an email sent to
yourphonenumber@vtext.com into a text message on that phone. This script
just sends a plain email using a free Gmail account.

SETUP (one-time)
-----------------
1. Use an existing Gmail account, or create a new free one just for this.

2. Create a Gmail "App Password" (required - your normal Gmail password
   won't work for this):
   - Go to https://myaccount.google.com/apppasswords
   - You may first need to enable 2-Step Verification on the account if
     it isn't already on (Google requires this before app passwords can
     be created).
   - Create a new app password, name it something like "sp500-script".
   - Copy the 16-character password it gives you (spaces don't matter).

3. Install dependencies (only yfinance is needed - email sending uses
   Python's built-in smtplib, no extra package required):
     pip install yfinance --break-system-packages

4. Set these environment variables:
     export GMAIL_ADDRESS="youraccount@gmail.com"
     export GMAIL_APP_PASSWORD="the16charapppassword"
     export PHONE_NUMBER="1234567890"        # your 10-digit number, no dashes
     export CARRIER_GATEWAY="vtext.com"      # Verizon. See CARRIER_GATEWAYS
                                              # below for other carriers.

5. Run it manually to test:
     python3 sp500_email_sms.py

6. Automate it daily - see the accompanying GitHub Actions workflow
   (daily-sp500-email-sms.yml) to run this in the cloud for free.

NOTES / HONEST CAVEATS
-----------------------
- Delivery isn't guaranteed to be instant - carriers sometimes delay
  these by a few minutes, and in rare cases a message may not arrive at
  all. There's no delivery confirmation like Twilio provides.
- If you ever switch carriers, update CARRIER_GATEWAY to match (see the
  dict below for the most common ones).
- Some carriers occasionally rate-limit or filter automated messages
  through this gateway if volume looks unusual - one message a day is
  very unlikely to trigger that.
"""

import os
import smtplib
import sys
from datetime import datetime
from email.mime.text import MIMEText

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
    "visible": "vtext.com",  # Visible runs on Verizon's network
}


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


def send_email_sms(body: str):
    gmail_address = os.environ["GMAIL_ADDRESS"]
    gmail_app_password = os.environ["GMAIL_APP_PASSWORD"]
    phone_number = os.environ["PHONE_NUMBER"]
    carrier_gateway = os.environ["CARRIER_GATEWAY"]

    to_address = f"{phone_number}@{carrier_gateway}"

    # Keep subject empty - most carrier gateways prepend the subject to
    # the text, which you don't want for a clean message.
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
        summary = get_sp500_summary()
    except Exception as e:
        print(f"[{datetime.now()}] Failed to fetch S&P 500 data: {e}", file=sys.stderr)
        sys.exit(1)

    print("Message to send:\n" + summary)

    required_vars = ["GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "PHONE_NUMBER", "CARRIER_GATEWAY"]
    missing = [v for v in required_vars if not os.environ.get(v)]
    if missing:
        print(f"\n[Not sent] Missing environment variables: {', '.join(missing)}")
        print("Set them and re-run to actually send the text.")
        return

    try:
        send_email_sms(summary)
        print("\nSent!")
    except Exception as e:
        print(f"[{datetime.now()}] Failed to send text: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
