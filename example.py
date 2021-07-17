import datetime
import json
import os
from decimal import Decimal

from tempoapiclient import client

from models import Consultant, BillMode

TEMPO_TOKEN = os.environ["TEMPO_TOKEN"]
TEMPO_BASE_URL = os.environ["TEMPO_BASE_URL"]


tempo = client.Tempo(auth_token=TEMPO_TOKEN, base_url=TEMPO_BASE_URL)

c = Consultant(billing_mode=BillMode.MONTHLY, rate=Decimal("9680"), tempo_instance=tempo)
payouts = c.invoices_in_range(
    start_date=datetime.date.fromisoformat("2021-06-01"), end_date=datetime.date.fromisoformat("2021-07-31")
)

json_response = {p.invoice_date.isoformat(): p.to_json() for p in payouts.values()}

print(json.dumps(json_response, indent=4))
