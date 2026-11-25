"""Build expected_moves.json: how much further a stock really went AFTER it was already up X% on the day.

For every NASDAQ/NYSE stock under $20, take the last ~60 days of 5-minute bars (premarket, regular and
after-hours). Each time a stock first reaches +20%, +30%, +50%, +75%, +100%, +150% or +200% on the day
while within 10% of its high (the same moment the scanner would alert), record:
  - further: the best price after that bar, until 20:00 ET, versus that price
  - close:   the last price of the day versus that price
The scanner turns these into an "expected left" line so you can see when most of the move is likely done.

Run:  python study_expected.py            (takes ~10 min; refresh weekly)
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date
from pathlib import Path

import scanner as sc

STEPS = [0.20, 0.30, 0.50, 0.75, 1.00, 1.50, 2.00]
NEAR_HIGH = 0.10
OUT = Path(__file__).with_name("expected_moves.json")


def fetch(http: sc.Http, sym: str):
    http.prime_yahoo()
    data = http.get_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
                         params={"interval": "5m", "range": "60d", "includePrePost": "true", "events": "split"},
                         headers=sc.YAHOO_HEADERS, source="yahoo")
    res = (((data or {}).get("chart") or {}).get("result") or [None])[0]
    return sc.parse_chart_result(res, sym), sc.parse_splits(res)


def events_for(s: sc.Series, splits: list[dict]) -> list[dict]:
    days: dict[str, list[int]] = defaultdict(list)
    for i, t in enumerate(s.ts):
        days[datetime.fromtimestamp(t, sc.NY).date().isoformat()].append(i)
    split_days = {x["d"] for x in splits}
    order = sorted(days)
    out = []
    for k in range(1, len(order)):
        d, pd = order[k], order[k - 1]
        if d in split_days or pd in split_days:
            continue
        reg = [i for i in days[pd] if sc.session_at(s.ts[i]) == "regular"]
        if not reg:
            continue
        prev = s.c[reg[-1]]
        idx = days[d]
        if prev <= 0 or len(idx) < 10 or max(s.h[i] for i in idx) / prev > 25:   # bad ticks
            continue
        hod, done = 0.0, set()
        for j, i in enumerate(idx):
            hod = max(hod, s.h[i])
            g = s.c[i] / prev - 1
            for st in STEPS:
                if st in done or g < st or s.c[i] < hod * (1 - NEAR_HIGH):
                    continue
                done.add(st)
                rest = idx[j + 1:]
                entry = s.c[i]
                further = (max(s.h[r] for r in rest) / entry - 1) if rest else 0.0
                out.append({"sym": s.symbol, "d": d, "step": st, "gain": g, "prev": prev,
                            "session": sc.session_at(s.ts[i]) or "?", "further": max(0.0, further),
                            "close": s.c[idx[-1]] / entry - 1})
    return out


def summarise(evs: list[dict]) -> dict:
    f = sorted(e["further"] for e in evs)
    q = statistics.quantiles(f, n=4) if len(f) >= 4 else [f[0], statistics.median(f), f[-1]]
    n = len(evs)
    return {"n": n, "med": round(statistics.median(f), 4), "p25": round(q[0], 4), "p75": round(q[2], 4),
            "hit10": round(sum(e["further"] >= 0.10 for e in evs) / n, 3),
            "hit20": round(sum(e["further"] >= 0.20 for e in evs) / n, 3),
            "hit50": round(sum(e["further"] >= 0.50 for e in evs) / n, 3),
            "below": round(sum(e["close"] < 0 for e in evs) / n, 3),
            "dec": [round(x, 4) for x in (statistics.quantiles(f, n=10) if n >= 10 else [])]}


def main() -> int:
    cfg = sc.Config()
    cfg.max_price, cfg.min_price = 20.0, 0.0
    http = sc.Http()
    uni = sc.fetch_universe(http, cfg)
    syms = sorted(uni)
    print(f"{len(syms)} stocks under $20", flush=True)
    evs: list[dict] = []
    got = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        for n, (s, splits) in enumerate(pool.map(lambda x: fetch(http, x), syms), 1):
            if s:
                got += 1
                evs += events_for(s, splits)
            if n % 250 == 0:
                print(f"  {n}/{len(syms)} · {len(evs)} events", flush=True)
    if not evs:
        print("no events — data feed down?")
        return 1
    table: dict[str, dict] = {}
    for band, keep in (("all", lambda e: True), ("under1", lambda e: e["prev"] < 1), ("1to20", lambda e: e["prev"] >= 1)):
        for sess in ("all", "extended", "regular"):
            for st in STEPS:
                sel = [e for e in evs if e["step"] == st and keep(e)
                       and (sess == "all" or (e["session"] == "regular") == (sess == "regular"))]
                if len(sel) >= 15:
                    table[f"{band}|{sess}|{st:g}"] = summarise(sel)
    span = sorted({e["d"] for e in evs})
    OUT.write_text(json.dumps({"built": date.today().isoformat(), "from": span[0], "to": span[-1],
                               "stocks": got, "events": len(evs), "near_high": NEAR_HIGH,
                               "table": table}, indent=1), encoding="utf-8")
    print(f"{got} stocks with data · {len(evs)} events · {span[0]} to {span[-1]}")
    for k, v in table.items():
        if k.startswith(("under1|all", "1to20|all", "all|all")):
            print(f"{k:22} n={v['n']:4}  median further {v['med']:+.0%}  p25 {v['p25']:+.0%}  p75 {v['p75']:+.0%}"
                  f"  +10%: {v['hit10']:.0%}  +20%: {v['hit20']:.0%}  closed below: {v['below']:.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
