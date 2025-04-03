import csv
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from os import environ
from imaplib import IMAP4_SSL
import email
import re
import sys

from bs4 import BeautifulSoup

host = environ.get("IMAP_HOST", "imap.gmail.com")
username = environ.get("IMAP_USERNAME")
password = environ.get("IMAP_PASSWORD")
imap_mailbox = environ.get("IMAP_MAILBOX", '"[Gmail]/All Mail"' if "gmail" in host else "INBOX")

if not username or not password:
    print("IMAP_USERNAME and IMAP_PASSWORD must be set")
    exit(1)


@dataclass
class Email:
    received: datetime
    from_: str
    to: str
    subject: str
    body_text: str
    body_html: str

def print_err(msg: str):
    print(msg, file=sys.stderr)

def decode_email(raw_data: bytes):
    data = email.message_from_bytes(raw_data)

    date_str = data["Date"]
    received = parsedate_to_datetime(date_str)
    
    msg = Email(
        received=received,
        from_=data["from"],
        to=data["to"],
        subject=data["subject"],
        body_text="",
        body_html="",
    )

    body_txt = ""
    body_html = ""
    
    if data.is_multipart():
        for part in data.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            
            if "attachment" in content_disposition:
                continue
            
            if content_type == "text/plain" or content_type == "text/html":
                try:
                    body_part: str = part.get_payload(decode=True).decode() # type: ignore
                    if content_type == "text/plain":
                        body_txt += body_part
                    elif content_type == "text/html":
                        body_html += body_part
                except:
                    pass
    else:
        body_txt = data.get_payload(decode=True).decode(errors='ignore') # type: ignore
    
    msg.body_text = body_txt
    msg.body_html = body_html
    
    return msg


def parse_data(email_body: str):
    doc = BeautifulSoup(email_body, "html.parser")
    
    tables = doc.find_all("table")
    for table in tables:
        rows = table.find_all("tr") # type: ignore
        for row in rows:
            cells = row.find_all("td") # type: ignore
            if len(cells) != 5:
                continue

            # cell 0, image

            description_cell = cells[1]
            # first div contains the description
            description_div = description_cell.find("div") # type: ignore
            if not description_div:
                continue
            description = description_div.get_text(strip=True) # type: ignore
            
            qty_cell = cells[2]

            # there are multiple spans here, the "display: none" has the decimal qty
            qty_span = cells[2].select_one('span[style*="none"]') # type: ignore
            if not qty_span:
                continue
            try:
                qty = qty_span.get_text(strip=True)
                qty = float(qty)
            except:
                continue
            
            # unit is the non-numerical bit
            unit = re.sub(r'[\d\.]+', '', qty_cell.get_text(strip=True))

            price = cells[3].get_text(strip=True)
            if not price.startswith("$"):
                continue
            price = price[1:]
            
            # "allow subs"
            
            yield description, qty, unit, price

SEARCH_TERMS = [
    "Thank you for shopping at Woolworths"
    # TODO parse the old countdown emails
]

csv_out = csv.writer(sys.stdout)
csv_out.writerow(["timestamp", "description", "qty", "unit", "price"])

with IMAP4_SSL("imap.gmail.com") as imap:

    imap.login(username, password)

    _, imap_list = imap.list()
    # print(imap_list)

    imap.select(imap_mailbox)

    for term in SEARCH_TERMS:

        escaped_term = term.replace('"', '""')
        result, data = imap.search(None, 'TEXT', f'"{escaped_term}"')

        email_ids: list[str] = data[0].split()

        for n, id in enumerate(reversed(email_ids)):
            print_err(f'Checking {n} of {len(email_ids)} results')
            _, data = imap.fetch(id, "(RFC822)")
            raw_email: bytes = data[0][1] # type: ignore

            msg = decode_email(raw_email)
            if (term not in msg.body_text) and (term not in msg.body_html):
                continue
            
            records = parse_data(msg.body_html or msg.body_text)
            for description, qty, unit, price in records:
                csv_out.writerow([
                    msg.received.strftime('%Y-%m-%d %H:%M:%S'),
                    description, 
                    qty, 
                    unit, 
                    price
                ])
