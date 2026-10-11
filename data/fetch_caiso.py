"""Fetch CAISO NP15 day-ahead LMPs from OASIS and merge into data/caiso_np15_dam_2026.json.

Rerunnable: uv run python data/fetch_caiso.py. Existing pairs are kept, new ones merged in.
"""
import csv, io, json, ssl, time, urllib.request, zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import certifi

OUT = Path(__file__).parent / "caiso_np15_dam_2026.json"
URL = ("https://oasis.caiso.com/oasisapi/SingleZip?queryname=PRC_LMP&startdatetime={s}&enddatetime={e}"
       "&version=1&market_run_id=DAM&node=TH_NP15_GEN-APND&resultformat=6")
START, END = datetime(2026, 4, 1, 7, tzinfo=timezone.utc), datetime(2026, 7, 1, 7, tzinfo=timezone.utc)
CHUNK = timedelta(days=30)


def fetch(s: datetime, e: datetime) -> dict[str, float]:
    f = "%Y%m%dT%H:%M-0000"
    ctx = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(URL.format(s=s.strftime(f), e=e.strftime(f)), context=ctx, timeout=120) as r:
        z = zipfile.ZipFile(io.BytesIO(r.read()))
    rows = csv.DictReader(io.TextIOWrapper(z.open(z.namelist()[0]), encoding="utf-8-sig"))
    return {r["INTERVALSTARTTIME_GMT"]: float(r["MW"]) for r in rows if r["LMP_TYPE"] == "LMP"}


def main():
    prices: dict[str, float] = {}
    if OUT.exists():
        prices.update(dict(json.loads(OUT.read_text())))
    t = START
    while t < END:
        e = min(t + CHUNK, END)
        got = fetch(t, e)
        print(t.date(), e.date(), len(got), "rows")
        prices.update(got)
        t = e
        if t < END:
            time.sleep(6)
    # sort on parsed time; OASIS and the seed file spell the offset differently
    keyed = {datetime.fromisoformat(k).astimezone(timezone.utc): v for k, v in prices.items()}
    pairs = [[t.strftime("%Y-%m-%dT%H:%M:%S-00:00"), keyed[t]] for t in sorted(keyed)]
    OUT.write_text(json.dumps(pairs))
    print(len(pairs), "hours", pairs[0][0], "->", pairs[-1][0])


main()
