from decimal import Decimal
from typing import Optional
import datetime
from fastapi import FastAPI, Header, HTTPException
import os

from tempoapiclient import client
from models import Consultant, BillMode

TEMPO_TOKEN = os.environ["TEMPO_TOKEN"]
TEMPO_BASE_URL = os.environ["TEMPO_BASE_URL"]

# Need's integration in bigger system
CONSULTANT_RATE = Decimal(str(os.environ["CONSULTANT_RATE"]))
CONSULTANT_BILLING_MODE = BillMode.MONTHLY if os.environ["CONSULTANT_BILLING_MODE"] == BillMode.MONTHLY.value else BillMode.HOURLY

# Don't judge me, I just want to get this working on local with minimum effort
TOKEN = os.environ["DONT_JUDGE_ITS_LOCAL_TOKEN"]

app = FastAPI()
tempo = client.Tempo(auth_token=TEMPO_TOKEN, base_url=TEMPO_BASE_URL)


@app.get("/invoices/")
def get_invoices(start_date: datetime.date, end_date: Optional[str] = None, token: Optional[str] = Header(None)):
    if token != TOKEN:
        raise HTTPException(status_code=401, detail="UnAuthorized!")
    c = Consultant(billing_mode=CONSULTANT_BILLING_MODE, rate=CONSULTANT_RATE, tempo_instance=tempo)
    payouts = c.invoices_in_range(start_date=start_date, end_date=end_date)

    return {p.invoice_date.isoformat(): p.to_json() for p in payouts.values()}
