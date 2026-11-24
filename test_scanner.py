"""Offline tests: simulated market data, no network needed.  Run:  python -m unittest -v"""
import math
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import os  # noqa: E402
os.environ.setdefault("UPSIDE_ONLY", "off")  # most tests cover the full alert set; TestUpsideOnly turns it on
import scanner as S  # noqa: E402

NY = S.NY


def et(y, mo, d, h, mi, s=0):
    return datetime(y, mo, d, h, mi, s, tzinfo=NY).timestamp()


NOW = et(2026, 11, 9, 8, 30)  # Monday premarket


def chart_json(sym, prev, bars):
    ts, o, h, l, c, v = zip(*bars)
    return {"chart": {"result": [{"meta": {"symbol": sym, "chartPreviousClose": prev},
                                  "timestamp": list(ts),
                                  "indicators": {"quote": [{"open": list(o), "high": list(h), "low": list(l),
                                                            "close": list(c), "volume": list(v)}]}}], "error": None}}


def parabolic_bars():
    """Flat around $0.42 from 04:00, then goes vertical 07:50→08:30 to ~$0.95 on huge volume."""
    bars, t = [], et(2026, 11, 9, 4, 0)
    price = 0.42
    while t <= NOW:
        mins_into_run = (t - et(2026, 11, 9, 7, 50)) / 60
        if mins_into_run < 0:
            p, vol = 0.42 + 0.002 * math.sin(t / 600), 3_000
        else:
            p, vol = 0.42 * math.exp(0.0005 * mins_into_run ** 2 + 0.002 * mins_into_run), 60_000 + 6_000 * mins_into_run
        bars.append((int(t), price, max(price, p) * 1.003, min(price, p) * 0.998, p, vol))
        price = p
        t += 60
    return bars


def flat_bars(level=0.55):
    bars, t = [], et(2026, 11, 9, 4, 0)
    while t <= NOW:
        p = level * (1 + 0.003 * math.sin(t / 300))
        bars.append((int(t), p, p * 1.002, p * 0.998, p, 2_000))
        t += 60
    return bars


def crash_bars():
    bars, t = [], et(2026, 11, 9, 4, 0)
    price = 0.80
    while t <= NOW:
        m = (t - et(2026, 11, 9, 8, 5)) / 60
        p = 0.80 if m < 0 else max(0.80 * (1 - 0.025 * m), 0.30)
        bars.append((int(t), price, max(p, price), min(p, price), p, 4_000 if m < 0 else 150_000))
        price = p
        t += 60
    return bars


UNIVERSE = {"data": {"rows": [
    {"symbol": "ROKT", "name": "Rocket Bio Inc. Common Stock", "lastsale": "$0.40", "netchange": "-0.01", "pctchange": "-2%", "volume": "1,200,000", "marketCap": "6,000,000"},
    {"symbol": "FLAT", "name": "Flatline Corp Common Stock", "lastsale": "$0.55", "netchange": "UNCH", "pctchange": "0%", "volume": "300,000"},
    {"symbol": "DOWN", "name": "Downhill Holdings Common Stock", "lastsale": "$0.80", "netchange": "0.02", "pctchange": "2%", "volume": "900,000"},
    {"symbol": "BIGC", "name": "Big Cap Co Common Stock", "lastsale": "$45.10", "netchange": "0.5", "pctchange": "1%", "volume": "9,000,000"},
    {"symbol": "ROKTW", "name": "Rocket Bio Inc. Warrants", "lastsale": "$0.02", "netchange": "0", "pctchange": "0%", "volume": "100"},
] + [{"symbol": f"Z{chr(65 + i // 26)}{chr(65 + i % 26)}", "name": f"Filler {i} Inc", "lastsale": "$0.50",
      "netchange": "0", "pctchange": "0%", "volume": "1000"} for i in range(30)]}}

SEC_ATOM = """<?xml version="1.0" encoding="ISO-8859-1" ?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>Latest Filings</title>
<entry>
<title>8-K - Rocket Bio Inc. (0001111111) (Filer)</title>
<link rel="alternate" type="text/html" href="https://www.sec.gov/Archives/edgar/data/1111111/000111111126000001-index.htm"/>
<summary type="html"> &lt;b&gt;Filed:&lt;/b&gt; 2026-11-09 &lt;b&gt;AccNo:&lt;/b&gt; 0001111111-26-000001 &lt;b&gt;Size:&lt;/b&gt; 300 KB&lt;br&gt;Item 1.01: Entry into a Material Definitive Agreement&lt;br&gt;Item 5.01: Changes in Control of Registrant</summary>
<updated>2026-11-09T08:10:00-05:00</updated>
<id>urn:tag:sec.gov,2008:accession-number=0001111111-26-000001</id>
</entry>
<entry>
<title>8-K - Downhill Holdings (0002222222) (Filer)</title>
<link rel="alternate" type="text/html" href="https://www.sec.gov/Archives/edgar/data/2222222/x-index.htm"/>
<summary type="html"> &lt;b&gt;Filed:&lt;/b&gt; 2026-11-09 &lt;br&gt;Item 1.03: Bankruptcy or Receivership</summary>
<updated>2026-11-09T08:00:00-05:00</updated>
<id>urn:tag:sec.gov,2008:accession-number=0002222222-26-000009</id>
</entry>
<entry>
<title>8-K - Big Cap Co (0003333333) (Filer)</title>
<link rel="alternate" type="text/html" href="https://www.sec.gov/x"/>
<summary type="html">Item 8.01: Other Events</summary>
<updated>2026-11-09T08:00:00-05:00</updated>
<id>urn:tag:sec.gov,2008:accession-number=0003333333-26-000001</id>
</entry>
</feed>"""

HALTS_RSS = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:ndaq="http://www.nasdaqtrader.com/"><channel><title>NASDAQTrader.com</title>
<item><title>FLAT</title>
<ndaq:HaltDate>11/09/2026</ndaq:HaltDate><ndaq:HaltTime>08:20:00</ndaq:HaltTime>
<ndaq:IssueSymbol>FLAT</ndaq:IssueSymbol><ndaq:IssueName>Flatline Corp</ndaq:IssueName>
<ndaq:Market>NASDAQ</ndaq:Market><ndaq:ReasonCode>T1</ndaq:ReasonCode>
<ndaq:PauseThresholdPrice></ndaq:PauseThresholdPrice><ndaq:ResumptionDate></ndaq:ResumptionDate>
<ndaq:ResumptionQuoteTime></ndaq:ResumptionQuoteTime><ndaq:ResumptionTradeTime></ndaq:ResumptionTradeTime>
</item>
<item><title>BIGC</title>
<ndaq:HaltDate>11/09/2026</ndaq:HaltDate><ndaq:HaltTime>08:21:00</ndaq:HaltTime>
<ndaq:IssueSymbol>BIGC</ndaq:IssueSymbol><ndaq:Market>NYSE</ndaq:Market><ndaq:ReasonCode>LUDP</ndaq:ReasonCode>
</item>
</channel></rss>"""

NEWS_RSS = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel><title>wire</title>
<item><title>Rocket Bio Announces FDA Approval of RB-101 for Rare Disease</title>
<link>https://example.com/rokt-fda</link><guid>gnw-1</guid>
<description>BOSTON, Nov. 09, 2026 -- Rocket Bio Inc. (NASDAQ: ROKT) today announced the U.S. FDA has approved...</description>
<pubDate>Mon, 09 Nov 2026 13:15:00 GMT</pubDate></item>
<item><title>Flatline Corp Announces Pricing of $3 Million Registered Direct Offering</title>
<link>https://example.com/flat-offering</link><guid>gnw-2</guid>
<description>Flatline Corp (Nasdaq: FLAT) announced pricing of a registered direct offering</description>
<pubDate>Mon, 09 Nov 2026 13:05:00 GMT</pubDate></item>
<item><title>Big Cap Co beats earnings</title><link>https://example.com/b</link><guid>gnw-3</guid>
<description>(NYSE: BIGC) record revenue</description><pubDate>Mon, 09 Nov 2026 13:00:00 GMT</pubDate></item>
</channel></rss>"""

CIK_JSON = {"0": {"cik_str": 1111111, "ticker": "ROKT", "title": "Rocket Bio"},
            "1": {"cik_str": 2222222, "ticker": "DOWN", "title": "Downhill"},
            "2": {"cik_str": 3333333, "ticker": "BIGC", "title": "Big Cap"}}


def daily_json(sym, base):
    t0 = et(2026, 8, 1, 16, 0)
    bars = []
    for i in range(70):
        p = base * (1 + 0.03 * math.sin(i))
        bars.append((int(t0 + i * 86400), p, p, p, p, 500_000))
    return chart_json(sym, base, bars)


class FakeHttp(S.Http):
    """Routes URLs to fixtures and captures outgoing alerts."""

    def __init__(self, spark_works=True):
        super().__init__()
        self.sent = []
        self.spark_works = spark_works
        self.charts = {"ROKT": chart_json("ROKT", 0.40, parabolic_bars()),
                       "FLAT": chart_json("FLAT", 0.55, flat_bars()),
                       "DOWN": chart_json("DOWN", 0.80, crash_bars())}

    def prime_yahoo(self):
        pass

    def get_json(self, url, params=None, headers=None, source="web", timeout=20):
        self._mark(source, True)
        if "screener/stocks" in url:
            return UNIVERSE if params["exchange"] == "nasdaq" else {"data": {"rows": []}}
        if "company_tickers" in url:
            return CIK_JSON
        if "/v7/finance/spark" in url:
            if not self.spark_works:
                self.health[source] = [0, 1]
                return {"finance": {"error": {"code": "Unauthorized"}}}
            res = []
            for sym in params["symbols"].split(","):
                cj = self.charts.get(sym)
                if cj:
                    r = cj["chart"]["result"][0]
                    # spark only has 5-minute closes
                    ts = r["timestamp"][::5]
                    cl = r["indicators"]["quote"][0]["close"][::5]
                    res.append({"symbol": sym, "response": [{"meta": r["meta"], "timestamp": ts,
                                                             "indicators": {"quote": [{"close": cl}]}}]})
            return {"spark": {"result": res, "error": None}}
        if "/v8/finance/chart/" in url:
            sym = url.rsplit("/", 1)[-1]
            if params.get("interval") == "1d":
                return daily_json(sym, {"ROKT": 0.4, "DOWN": 0.8}.get(sym, 0.5))
            return self.charts.get(sym)
        if "/api/quote/" in url:
            return {"data": {"primaryData": {"bidPrice": "$0.9400", "askPrice": "$0.9550"}}}
        return None

    def get_text(self, url, params=None, headers=None, source="web", timeout=20):
        self._mark(source, True)
        if "browse-edgar" in url:
            return SEC_ATOM if params["type"] == "8-K" else '<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        if "nasdaqtrader" in url:
            return HALTS_RSS
        if "globenewswire" in url:
            return NEWS_RSS
        if "prnewswire" in url or "feeds.finance.yahoo" in url:
            return '<rss><channel></channel></rss>'
        return None

    def post(self, url, json_body=None, data=None, headers=None):
        self.sent.append((url, json_body, data, headers))
        return True


def make_scanner(http=None, tmp=None, clock=NOW):
    cfg = S.Config()
    cfg.telegram_token, cfg.telegram_chat = "T", "C"
    cfg.discord_webhook = "https://discord.example/hook"
    cfg.ntfy_topic = "topic"
    http = http or FakeHttp()
    st = S.State(Path(tmp) / "state.json")
    n = S.Notifier(cfg, http)
    S.time.sleep = lambda *_: None  # speed: no Telegram pacing / SEC pacing in tests
    sc = S.Scanner(cfg, http, st, n, clock=lambda: clock)
    return sc, http, st


class TestCalendar(unittest.TestCase):
    def test_sessions_winter(self):
        self.assertEqual(S.session_at(et(2026, 11, 9, 3, 59)), None)
        self.assertEqual(S.session_at(et(2026, 11, 9, 4, 0)), "premarket")
        self.assertEqual(S.session_at(et(2026, 11, 9, 9, 30)), "regular")
        self.assertEqual(S.session_at(et(2026, 11, 9, 16, 0)), "afterhours")
        self.assertEqual(S.session_at(et(2026, 11, 9, 20, 0)), None)

    def test_weekend_holiday_earlyclose(self):
        self.assertIsNone(S.session_at(et(2026, 11, 14, 10, 0)))       # Saturday
        self.assertIsNone(S.session_at(et(2026, 11, 26, 10, 0)))       # Thanksgiving
        self.assertEqual(S.session_at(et(2026, 11, 27, 13, 30)), "afterhours")  # early close
        self.assertIsNone(S.session_at(et(2026, 11, 27, 17, 30)))

    def test_summer_time(self):
        # 08:00 UTC in July = 04:00 EDT premarket open
        ts = datetime(2027, 7, 13, 8, 0, tzinfo=S.timezone.utc).timestamp()
        self.assertEqual(S.session_at(ts), "premarket")


class TestParsing(unittest.TestCase):
    def test_universe_filters(self):
        http = FakeHttp()
        uni = S.fetch_universe(http, S.Config())
        self.assertIn("ROKT", uni)
        self.assertNotIn("BIGC", uni)       # over $1
        self.assertNotIn("ROKTW", uni)      # warrant
        self.assertAlmostEqual(uni["ROKT"]["prev"], 0.41)
        self.assertAlmostEqual(uni["FLAT"]["prev"], 0.55)

    def test_spark_shapes(self):
        v7 = {"spark": {"result": [{"symbol": "AAA", "response": [{"meta": {"chartPreviousClose": 0.5},
              "timestamp": [1, 2], "indicators": {"quote": [{"close": [0.5, None]}]}}]}]}}
        v8 = {"BBB": {"symbol": "BBB", "timestamp": [1, 2], "close": [0.3, 0.33], "chartPreviousClose": 0.3}}
        self.assertEqual(S.parse_spark(v7)["AAA"].c, [0.5])
        self.assertEqual(S.parse_spark(v8)["BBB"].c, [0.3, 0.33])
        self.assertEqual(S.parse_spark({"finance": {"error": {}}}), {})

    def test_sec(self):
        cats = S.parse_sec_atom(SEC_ATOM, {"0001111111": "ROKT", "0002222222": "DOWN"})
        by = {c.symbol: c for c in cats}
        self.assertEqual(by["ROKT"].kind, "bullish")
        self.assertEqual(by["ROKT"].weight, 3)
        self.assertIn("Change in control", by["ROKT"].title)
        self.assertEqual(by["DOWN"].kind, "blackswan")
        self.assertNotIn("BIGC", by)

    def test_halts(self):
        cats = S.parse_halts(HALTS_RSS, {"FLAT": {}})
        self.assertEqual(len(cats), 1)
        self.assertEqual(cats[0].title, "T1: News pending")
        self.assertIn("no resumption", cats[0].detail)

    def test_headlines(self):
        self.assertEqual(S.classify_headline("XYZ files voluntary Chapter 11 petitions")[0], "blackswan")
        self.assertEqual(S.classify_headline("Company receives FDA approval for drug")[:2], ("bullish", 5))
        self.assertEqual(S.classify_headline("Announces pricing of $5M registered direct offering")[0], "bearish")
        self.assertEqual(S.classify_headline("FDA issues Complete Response Letter")[0], "blackswan")
        self.assertEqual(S.classify_headline("Company to host webcast")[0], "neutral")
        items = S.parse_rss(NEWS_RSS)
        cats = S.news_catalysts(items, "GNW", {"ROKT": {}, "FLAT": {}})
        self.assertEqual({c.symbol for c in cats}, {"ROKT", "FLAT"})


class TestAnalysis(unittest.TestCase):
    def test_parabolic_scores_high(self):
        s = S.parse_chart_result(chart_json("ROKT", 0.40, parabolic_bars())["chart"]["result"][0])
        a = S.analyze(s, 0.40)
        self.assertGreater(a.day_gain, 0.9)
        self.assertGreater(a.g15, 0.15)
        self.assertGreater(a.accel, 1.2)
        self.assertGreater(a.rel_vol, 5)
        self.assertGreaterEqual(a.score, 75)

    def test_flat_scores_low(self):
        s = S.parse_chart_result(chart_json("FLAT", 0.55, flat_bars())["chart"]["result"][0])
        a = S.analyze(s, 0.55)
        self.assertLess(a.score, 30)

    def test_cooldown(self):
        with tempfile.TemporaryDirectory() as d:
            st = S.State(Path(d) / "s.json")
            self.assertTrue(st.should_alert("PARABOLIC", "X", 0.5, 1000, 30, 0.25))
            st.record_alert("PARABOLIC", "X", 0.5, 1000)
            self.assertFalse(st.should_alert("PARABOLIC", "X", 0.55, 1300, 30, 0.25))
            self.assertTrue(st.should_alert("PARABOLIC", "X", 0.65, 1300, 30, 0.25))   # new leg up
            self.assertTrue(st.should_alert("PARABOLIC", "X", 0.5, 1000 + 1801, 30, 0.25))


class TestEndToEnd(unittest.TestCase):
    def run_cycle(self, http=None):
        with tempfile.TemporaryDirectory() as d:
            sc, http, st = make_scanner(http, d)
            self.assertGreater(sc.load_universe(), 20)
            alerts = sc.cycle()
            st.save()
            again = sc.cycle()          # same data again: nothing should repeat
            return alerts, again, http, sc

    def test_full_cycle(self):
        alerts, again, http, sc = self.run_cycle()
        got = {(a.kind, a.symbol) for a in alerts}
        self.assertIn(("PARABOLIC", "ROKT"), got)
        self.assertIn(("BLACKSWAN", "DOWN"), got)          # 8-K item 1.03 bankruptcy
        self.assertIn(("HALT", "FLAT"), got)               # T1 news pending
        self.assertIn(("CATALYST", "FLAT"), got)           # registered direct offering
        self.assertNotIn(("CATALYST", "ROKT"), got)        # folded into the parabolic alert
        self.assertNotIn("BIGC", {a.symbol for a in alerts})
        self.assertTrue(any(k in ("CRASH", "BLACKSWAN") and s == "DOWN" for k, s in got))
        rokt = next(a for a in alerts if a.kind == "PARABOLIC")
        text = "\n".join(rokt.lines)
        self.assertIn("Catalyst:", text)
        self.assertIn("Bid/ask", text)
        self.assertEqual(again, [])
        # each alert went to all three channels
        urls = [u for u, *_ in http.sent]
        self.assertTrue(any("api.telegram.org" in u for u in urls))
        self.assertTrue(any("discord" in u for u in urls))
        self.assertTrue(any("ntfy.sh/topic" in u for u in urls))
        for u, body, data, headers in http.sent:
            if headers:  # ntfy headers must be latin-1 encodable
                for v in headers.values():
                    v.encode("latin-1")
        print("\n--- sample alerts ---")
        for a in alerts:
            print(f"{S.EMOJI[a.kind]} {S.LABEL[a.kind]}: {a.symbol} — {a.title}")
            for line in a.lines:
                print("   ", line)

    def test_fallback_when_batch_feed_blocked(self):
        alerts, _, _, _ = self.run_cycle(FakeHttp(spark_works=False))
        self.assertIn(("PARABOLIC", "ROKT"), {(a.kind, a.symbol) for a in alerts})

    def test_heartbeat_and_warning(self):
        with tempfile.TemporaryDirectory() as d:
            sc, http, st = make_scanner(None, d)
            sc.load_universe()
            sc.http.health["yahoo"] = [0, 5]
            sc.notices("premarket", NOW)
            titles = [h.get("Title", "") for _, _, _, h in http.sent if h]
            self.assertTrue(any("online" in t for t in titles))
            self.assertTrue(any("yahoo unreachable" in t for t in titles))
            n = len(http.sent)
            sc.notices("premarket", NOW)       # not repeated the same day/session
            self.assertEqual(len(http.sent), n)


class TestTelegramChatDiscovery(unittest.TestCase):
    def test_finds_and_remembers_chat_id(self):
        class TG(FakeHttp):
            calls = 0

            def get_json(self, url, params=None, headers=None, source="web", timeout=20):
                if "getUpdates" in url:
                    TG.calls += 1
                    return {"ok": True, "result": [{"update_id": 1, "message": {"chat": {"id": 7123456789}, "text": "hi"}}]}
                return super().get_json(url, params, headers, source, timeout)

        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "state.json"
            cfg = S.Config()
            cfg.telegram_token, cfg.telegram_chat = "T", ""
            S.resolve_telegram_chat(cfg, TG(), p)
            self.assertEqual(cfg.telegram_chat, "7123456789")
            st = S.State(p)                      # scanner state keeps it
            st.save()
            cfg2 = S.Config()
            cfg2.telegram_token, cfg2.telegram_chat = "T", ""
            S.resolve_telegram_chat(cfg2, TG(), p)
            self.assertEqual(cfg2.telegram_chat, "7123456789")
            self.assertEqual(TG.calls, 1)        # second time read from saved state


if __name__ == "__main__":
    unittest.main()


# ───────────────────────── buy / sell signals ─────────────────────────

def flag_bars(break_out=True):
    """$0.40 → run to $0.80 (07:30–07:55), orderly pullback to ~$0.70 on light volume, then breakout."""
    bars, t = [], et(2026, 11, 9, 4, 0)
    end = et(2026, 11, 9, 8, 11)
    prev = 0.42
    while t <= end:
        m = (t - et(2026, 11, 9, 7, 30)) / 60
        if m < 0:
            p, v = 0.42, 3_000
        elif m <= 25:
            p, v = 0.42 + (0.80 - 0.42) * (m / 25), 120_000
        elif m <= 40:
            p, v = 0.80 - 0.10 * ((m - 25) / 15), 30_000          # pullback to 0.70
        else:
            p, v = (0.83 if break_out else 0.705), (150_000 if break_out else 20_000)
        h = max(prev, p) * 1.002
        lo = min(prev, p) * 0.998
        bars.append((int(t), prev, h, lo, p, v))
        prev = p
        t += 60
    return bars


def series_from(bars, prev=0.40, sym="FLAG"):
    return S.parse_chart_result(chart_json(sym, prev, bars)["chart"]["result"][0])


class TestTradeSignals(unittest.TestCase):
    def setUp(self):
        self.cfg = S.Config()

    def test_pullback_breakout_buy(self):
        s = series_from(flag_bars())
        a = S.analyze(s, 0.40)
        st = S.find_buy_setup(s, a, self.cfg)
        self.assertIsNotNone(st)
        self.assertEqual(st.name, "Pullback breakout")
        self.assertAlmostEqual(st.entry, 0.83, places=3)
        self.assertLess(st.stop, 0.70)
        self.assertGreater(st.t1, st.entry)
        self.assertGreater(st.t2, st.t1)

    def test_no_buy_without_breakout(self):
        s = series_from(flag_bars(break_out=False))
        self.assertIsNone(S.find_buy_setup(s, S.analyze(s, 0.40), self.cfg))

    def test_no_buy_into_vertical_spike(self):
        s = series_from(parabolic_bars(), sym="ROKT")
        self.assertIsNone(S.find_buy_setup(s, S.analyze(s, 0.40), self.cfg))

    def _exit(self, tr, price, now_off=600):
        base = flag_bars()
        t_last = base[-1][0]
        bars = base + [(t_last + 60, base[-1][4], max(price, base[-1][4]), min(price, base[-1][4]), price, 50_000)]
        s = series_from(bars)
        a = S.analyze(s, 0.40)
        return S.check_exit(tr, s, a, self.cfg, tr["ts"] + now_off)

    def new_trade(self):
        t_entry = flag_bars()[-1][0]
        return {"d": "2026-11-09", "ts": t_entry, "open": True, "setup": "Pullback breakout", "entry": 0.83,
                "stop": 0.686, "t1": 1.118, "t2": 1.262, "high": 0.83}

    def test_stop_hit(self):
        kind, reason, closes = self._exit(self.new_trade(), 0.66)
        self.assertEqual((kind, closes), ("STOP", True))

    def test_target1_then_breakeven(self):
        tr = self.new_trade()
        kind, reason, closes = self._exit(tr, 1.13)
        self.assertEqual((kind, closes), ("TRIM", False))
        self.assertEqual(tr["stop"], 0.83)          # moved to breakeven
        kind, reason, closes = self._exit(tr, 0.82)
        self.assertEqual((kind, closes), ("SELL", True))

    def test_trailing_stop_after_target(self):
        tr = self.new_trade()
        tr.update(t1_hit=True, stop=0.83, high=1.20)
        kind, reason, closes = self._exit(tr, 1.03)   # >12% off the 1.20 high
        self.assertEqual((kind, closes), ("SELL", True))
        self.assertIn("Trailing", reason)

    def test_time_stop(self):
        tr = self.new_trade()
        kind, reason, closes = self._exit(tr, 0.80, now_off=50 * 60)
        self.assertEqual((kind, closes), ("SELL", True))
        self.assertIn("Time stop", reason)

    def test_end_to_end_buy_then_sell(self):
        with tempfile.TemporaryDirectory() as d:
            http = FakeHttp()
            http.charts["ROKT"] = chart_json("ROKT", 0.40, flag_bars())
            t_buy = flag_bars()[-1][0]
            sc, http, st = make_scanner(http, d, clock=t_buy + 30)
            sc.load_universe()
            alerts = sc.cycle()
            buys = [a for a in alerts if a.kind == "BUY"]
            self.assertEqual([a.symbol for a in buys], ["ROKT"])
            self.assertTrue(st.d["trades"]["ROKT"]["open"])
            print("\n--- buy alert ---")
            for line in [buys[0].title] + buys[0].lines:
                print("   ", line)
            # price collapses through the stop → STOP alert
            bars = flag_bars() + [(t_buy + 60, 0.83, 0.83, 0.64, 0.65, 90_000)]
            http.charts["ROKT"] = chart_json("ROKT", 0.40, bars)
            sc.clock = lambda: t_buy + 120
            alerts = sc.cycle()
            stops = [a for a in alerts if a.kind == "STOP"]
            self.assertEqual([a.symbol for a in stops], ["ROKT"])
            self.assertFalse(st.d["trades"]["ROKT"]["open"])
            print("--- stop alert ---")
            for line in [stops[0].title] + stops[0].lines:
                print("   ", line)
            # no immediate re-buy during cooldown
            http.charts["ROKT"] = chart_json("ROKT", 0.40, flag_bars())
            self.assertFalse([a for a in sc.cycle() if a.kind == "BUY"])


class TestRunnerPotential(unittest.TestCase):
    def test_score_favours_small_cap_catalyst_runner(self):
        s = series_from(flag_bars())
        a = S.analyze(s, 0.40)
        cats = [{"kind": "bullish", "w": 5, "title": "FDA approval", "src": "GNW", "ts": NOW - 600}]
        small = {"last": 0.40, "mcap": 6e6}
        big = {"last": 0.40, "mcap": 400e6}
        hi, why = S.runner_score(a, small, {"avgvol": 300_000}, cats, "premarket", NOW)
        lo, _ = S.runner_score(a, big, {"avgvol": 30_000_000}, [], "premarket", NOW)
        self.assertGreaterEqual(hi, 80)
        self.assertLess(lo, 50)
        self.assertTrue(any("mcap" in w for w in why))
        diluted, _ = S.runner_score(a, small, {"avgvol": 300_000},
                                    cats + [{"kind": "bearish", "w": 3, "title": "offering", "src": "x", "ts": NOW}],
                                    "premarket", NOW)
        self.assertLess(diluted, hi)

    def test_runner_alert_fires_once(self):
        with tempfile.TemporaryDirectory() as d:
            http = FakeHttp()
            # early runner: +40%, trending, above VWAP
            bars, t, prev = [], et(2026, 11, 9, 4, 0), 0.40
            while t <= et(2026, 11, 9, 7, 0):
                m = (t - et(2026, 11, 9, 6, 30)) / 60
                p, v = (0.40, 2_000) if m < 0 else (0.40 * (1 + 0.40 * m / 30), 80_000)
                bars.append((int(t), prev, max(p, prev) * 1.002, min(p, prev) * 0.998, p, v))
                prev, t = p, t + 60
            http.charts["ROKT"] = chart_json("ROKT", 0.40, bars)
            sc, http, st = make_scanner(http, d, clock=et(2026, 11, 9, 7, 0, 30))
            sc.load_universe()
            kinds = [(a.kind, a.symbol) for a in sc.cycle()]
            self.assertIn(("RUNNER", "ROKT"), kinds)
            self.assertNotIn(("RUNNER", "ROKT"), [(a.kind, a.symbol) for a in sc.cycle()])



def premarket_runner_bars(end_h=7, end_m=0, tail=None):
    """Real Yahoo shape: premarket 1-minute bars with ZERO volume. Flat $0.40 from 04:00, takes off at 06:30."""
    bars, t, prev = [], et(2026, 11, 9, 4, 0), 0.40
    while t <= et(2026, 11, 9, end_h, end_m):
        m = (t - et(2026, 11, 9, 6, 30)) / 60
        p = 0.40 if m < 0 else 0.40 * (1 + 0.40 * min(m, 30) / 30)
        if tail and m > 30:
            p = tail(m - 30)
        bars.append((int(t), prev, max(p, prev) * 1.002, min(p, prev) * 0.998, p, 0))
        prev, t = p, t + 60
    return bars


class ExtendedHttp(FakeHttp):
    """FakeHttp plus Nasdaq's extended-trading feed (premarket trades with share volume)."""

    def __init__(self, feed_up=True):
        super().__init__()
        self.feed_up = feed_up
        self.ext_calls = 0

    def get_json(self, url, params=None, headers=None, source="web", timeout=20):
        if "/extended-trading" in url:
            self.ext_calls += 1
            if not self.feed_up:
                return None
            rows = []
            t = et(2026, 11, 9, 4, 0)
            while t <= et(2026, 11, 9, 9, 29):
                hm = datetime.fromtimestamp(t, NY)
                shares = 2_000 if hm.hour < 6 or (hm.hour == 6 and hm.minute < 30) else 80_000
                rows.append({"time": hm.strftime("%H:%M:15"), "price": "$0.50", "shareVolume": f"{shares:,}"})
                t += 60
            return {"data": {"tradeDetailTable": {"rows": rows[::-1]}}}
        return super().get_json(url, params, headers, source, timeout)


class TestExtendedHours(unittest.TestCase):
    def test_extended_volume_parsed_per_minute(self):
        class H(S.Http):
            def get_json(self, *a, **k):
                return {"data": {"tradeDetailTable": {"rows": [
                    {"time": "07:01:59", "shareVolume": "1,000"}, {"time": "07:01:02", "shareVolume": "500"},
                    {"time": "07:02:30", "shareVolume": "20"}, {"time": "bad", "shareVolume": "9"}]}}}
        day = datetime(2026, 11, 9).date()
        vols = S.fetch_extended_volume(H(), "X", "premarket", day)
        self.assertEqual(vols, {int(et(2026, 11, 9, 7, 1)): 1500.0, int(et(2026, 11, 9, 7, 2)): 20.0})
        self.assertIsNone(S.fetch_extended_volume(H(), "X", "regular", day))
        s = series_from([(int(et(2026, 11, 9, 7, 1)), .4, .4, .4, .4, 0), (int(et(2026, 11, 9, 7, 3)), .4, .4, .4, .4, 0)])
        self.assertEqual(S.fill_volume(s, vols), 1)
        self.assertEqual(s.v, [1500.0, 0])

    def _runner(self, http, clock):
        http.charts["ROKT"] = chart_json("ROKT", 0.40, premarket_runner_bars(7, 0))
        d = tempfile.mkdtemp()
        sc, http, st = make_scanner(http, d, clock=clock)
        sc.load_universe()
        return sc, http, st

    def test_premarket_runner_with_zero_yahoo_volume_gets_buy_plan(self):
        sc, http, st = self._runner(ExtendedHttp(), et(2026, 11, 9, 7, 0, 30))
        alerts = {(a.kind, a.symbol): a for a in sc.cycle()}
        self.assertGreater(http.ext_calls, 0)
        self.assertIn(("RUNNER", "ROKT"), alerts)
        text = " | ".join(alerts[("RUNNER", "ROKT")].lines)
        self.assertIn("Buy zone", text)
        self.assertIn("Stop", text)
        self.assertIn("limit orders", text)
        tr = st.d["trades"]["ROKT"]
        self.assertTrue(tr["open"])
        self.assertEqual(tr["setup"], "Runner")
        self.assertLess(tr["stop"], tr["entry"])
        self.assertGreaterEqual(tr["stop"], tr["entry"] * (1 - sc.cfg.max_risk_pct) - 1e-9)

    def test_runner_stop_then_fires_stop_alert(self):
        sc, http, st = self._runner(ExtendedHttp(), et(2026, 11, 9, 7, 0, 30))
        sc.cycle()
        stop = st.d["trades"]["ROKT"]["stop"]
        # price collapses below the stop by 07:10
        http.charts["ROKT"] = chart_json("ROKT", 0.40, premarket_runner_bars(7, 10, tail=lambda m: stop * 0.9))
        sc.clock = lambda: et(2026, 11, 9, 7, 10, 30)
        kinds = [(a.kind, a.symbol) for a in sc.cycle()]
        self.assertIn(("STOP", "ROKT"), kinds)
        self.assertFalse(st.d["trades"]["ROKT"]["open"])

    def test_feed_down_still_alerts_on_price(self):
        sc, http, st = self._runner(ExtendedHttp(feed_up=False), et(2026, 11, 9, 7, 0, 30))
        self.assertIn(("RUNNER", "ROKT"), [(a.kind, a.symbol) for a in sc.cycle()])


def fade_bars(minutes=45, bounce=0):
    """parabolic_bars() to 08:30, then a steady fade with weak bounces (lower highs, lower lows),
    heavier volume on the down bars. Optionally finish with `bounce` minutes of a strong recovery."""
    bars = parabolic_bars()
    t0, prev = bars[-1][0], bars[-1][4]
    peak = prev
    for m in range(1, minutes + 1):
        p = peak * (1 - 0.012 * m) * (1 + 0.008 * math.sin(m / 1.5))
        v = 90_000 if p < prev else 25_000
        bars.append((t0 + 60 * m, prev, max(p, prev) * 1.002, min(p, prev) * 0.998, p, v))
        prev = p
    for k in range(1, bounce + 1):
        p = prev * 1.025
        bars.append((t0 + 60 * (minutes + k), prev, p * 1.002, prev * 0.999, p, 70_000))
        prev = p
    return bars


class TestExitWatch(unittest.TestCase):
    def setUp(self):
        self.cfg = S.Config()

    def watch_entry(self):
        return {"kind": "PARABOLIC", "t": NOW, "price": 0.95, "high": 0.95}

    def assess(self, bars):
        s = series_from(bars, sym="ROKT")
        a = S.analyze(s, 0.40)
        return S.assess_exit(s, a, self.watch_entry(), self.cfg, bars[-1][0])

    def test_fade_triggers_exit(self):
        ok, bear, rec = self.assess(fade_bars())
        self.assertTrue(ok, (bear, rec))
        self.assertGreaterEqual(len(bear), 3)
        self.assertTrue(any("VWAP" in b for b in bear))

    def test_still_running_no_exit(self):
        ok, bear, rec = self.assess(parabolic_bars())
        self.assertFalse(ok)

    def test_bounce_blocks_exit(self):
        ok, bear, rec = self.assess(fade_bars(bounce=8))
        self.assertFalse(ok)
        self.assertTrue(rec)

    def test_bullish_news_blocks_exit(self):
        bars = fade_bars()
        s = series_from(bars, sym="ROKT")
        a = S.analyze(s, 0.40)
        cats = [{"kind": "bullish", "w": 5, "title": "Buyout agreement", "ts": bars[-1][0] - 300}]
        ok, _, rec = S.assess_exit(s, a, self.watch_entry(), self.cfg, bars[-1][0], None, cats)
        self.assertFalse(ok)
        self.assertTrue(any("bullish" in r for r in rec))

    def test_end_to_end_parabolic_then_exit_once(self):
        with tempfile.TemporaryDirectory() as d:
            sc, http, st = make_scanner(None, d)
            sc.load_universe()
            kinds = {(a.kind, a.symbol) for a in sc.cycle()}
            self.assertIn(("PARABOLIC", "ROKT"), kinds)
            self.assertIn("ROKT", st.d["watch"])
            self.assertIn("DOWN", st.d["watch"])            # black swan is watched too
            self.assertNotIn("FLAT", st.d["watch"])         # halts / catalysts are not
            # 45 minutes later the run has faded
            bars = fade_bars()
            http.charts["ROKT"] = chart_json("ROKT", 0.40, bars)
            sc.clock = lambda: bars[-1][0] + 30
            exits = [a for a in sc.cycle() if a.kind == "EXIT" and a.symbol == "ROKT"]
            self.assertEqual(len(exits), 1)
            text = "\n".join(exits[0].lines)
            self.assertIn("consider selling", text)
            self.assertIn("PARABOLIC", text)
            print("\n--- exit alert ---")
            for line in [exits[0].title] + exits[0].lines:
                print("   ", line)
            # no repeat on the next cycle
            self.assertFalse([a for a in sc.cycle() if a.kind == "EXIT" and a.symbol == "ROKT"])
            # survives a restart (state file) and is dropped after the watch window
            st.save()
            st2 = S.State(Path(d) / "state.json")
            st2.prune(NOW + 6 * 86400, 5)
            self.assertNotIn("ROKT", st2.d["watch"])

    def test_exit_alerts_can_be_turned_off(self):
        with tempfile.TemporaryDirectory() as d:
            sc, http, st = make_scanner(None, d)
            sc.cfg.exit_alerts = False
            sc.load_universe()
            sc.cycle()
            self.assertEqual(st.d.get("watch"), {})


SPLIT_DAY = et(2026, 11, 9, 0, 0)


class SplitHttp(ExtendedHttp):
    """ROKT did a 1:20 reverse split today: Nasdaq shows the real (adjusted) price, Yahoo's intraday
    previous close is still the old $0.40, so the chart looks like +2,700%."""

    def __init__(self, split_event=True, nasdaq_adjusted=True):
        super().__init__()
        self.split_event = split_event
        self.nasdaq_adjusted = nasdaq_adjusted
        self.charts["ROKT"] = chart_json("ROKT", 0.40, [(t, o * 20, h * 20, l * 20, c * 20, v)
                                                        for t, o, h, l, c, v in premarket_runner_bars(7, 0)])

    def get_json(self, url, params=None, headers=None, source="web", timeout=20):
        if "screener/stocks" in url and params["exchange"] == "nasdaq":
            rows = [dict(r) for r in UNIVERSE["data"]["rows"]]
            if self.nasdaq_adjusted:
                rows[0].update(lastsale="$11.20", netchange="3.20")   # Nasdaq: prev $8.00, split-adjusted
            rows += [{"symbol": f"M{chr(65 + i // 26)}{chr(65 + i % 26)}", "name": f"Mid {i} Inc",
                      "lastsale": "$5.00", "netchange": "0", "pctchange": "0%", "volume": "1000"} for i in range(25)]
            return {"data": {"rows": rows}}
        res = super().get_json(url, params, headers, source, timeout)
        if "/v8/finance/chart/ROKT" in url and params.get("interval") == "1d":
            res = daily_json("ROKT", 8.0)   # Yahoo daily history is split-adjusted
            if self.split_event:
                res["chart"]["result"][0]["events"] = {"splits": {str(int(SPLIT_DAY)): {
                    "date": int(SPLIT_DAY), "numerator": 1, "denominator": 20, "splitRatio": "1:20"}}}
        return res


class TestReverseSplit(unittest.TestCase):
    def test_split_adjusted_prev(self):
        sp = [{"d": "2026-11-18", "ratio": "1:35", "factor": 35.0}]
        fix = S.split_adjusted_prev(0.097, 3.50, sp, "2026-11-18")
        self.assertAlmostEqual(fix[0], 0.097 * 35)
        self.assertIn("1:35 reverse split", fix[1])
        self.assertIsNone(S.split_adjusted_prev(0.097, 3.50, sp, "2026-11-30"))      # old split: not today's move
        self.assertIsNone(S.split_adjusted_prev(0.20, 0.30, sp, "2026-11-18"))       # real +50%, price never jumped ×35
        self.assertIsNone(S.split_adjusted_prev(0.20, 0.45, [], "2026-11-18", 0.20))  # real run, Nasdaq agrees
        fb = S.split_adjusted_prev(0.10, 2.10, [], "2026-11-18", 2.00, 2.05)         # no split data: Nasdaq fallback
        self.assertEqual(fb[0], 2.00)
        # WETO 23 Nov 2026, real data: real +213% run, but Nasdaq's screener row was a day stale
        self.assertIsNone(S.split_adjusted_prev(0.1722, 0.5385, [], "2026-11-23", 0.4998, 0.1584))
        fwd = S.split_adjusted_prev(10.0, 5.1, [{"d": "2026-11-18", "ratio": "2:1", "factor": 0.5}], "2026-11-18")
        self.assertAlmostEqual(fwd[0], 5.0)                                          # forward split isn't a crash

    def _kinds(self, http, min_price=0.0, max_price=1.0):
        d = tempfile.mkdtemp()
        sc, http, st = make_scanner(http, d, clock=et(2026, 11, 9, 7, 0, 30))
        sc.cfg.min_price, sc.cfg.max_price = min_price, max_price
        sc.load_universe()
        return sc, {(a.kind, a.symbol): a for a in sc.cycle()}

    def test_reverse_split_is_not_a_runner_under_1(self):
        # early premarket on split day Nasdaq may still list the old $0.40 price, so the stock IS in the
        # under-$1 universe and only Yahoo's split event can unmask the fake +2,700%
        for event, adjusted in ((True, False), (True, True), (False, True)):
            sc, alerts = self._kinds(SplitHttp(split_event=event, nasdaq_adjusted=adjusted))
            self.assertEqual("ROKT" in sc.universe, not adjusted)
            for kind in ("PARABOLIC", "RUNNER", "BUY"):
                self.assertNotIn((kind, "ROKT"), alerts, f"split_event={event}")

    def test_1_to_20_band_sees_real_move_after_split(self):
        sc, alerts = self._kinds(SplitHttp(), 1.0, 20.0)
        self.assertIn("ROKT", sc.universe)
        self.assertNotIn("FLAT", sc.universe)     # $0.55 belongs to the under-$1 scanner
        self.assertNotIn("BIGC", sc.universe)     # $45 is above the band
        a = alerts.get(("RUNNER", "ROKT"))
        self.assertIsNotNone(a)
        self.assertIn("1:20 reverse split", " | ".join(a.lines))
        self.assertLess(sc.last_quick["ROKT"][1], 0.5)   # real +40%, not +2,700%

class TestBlackSwanTrend(unittest.TestCase):
    """A price-only black swan must not be a stock that was already crashing (SRTM / SAFX, 24 Nov 2026)."""

    def test_prior_trend(self):
        srtm = [1.53, 1.575, 1.287, 1.305, 1.098, 1.125, 1.161, 0.882, 0.756, 1.03]   # real closes
        safx = [0.078, 0.072, 0.07, 0.072, 0.078, 0.045, 0.05, 0.046, 0.042, 0.052]
        self.assertLess(S.prior_trend(srtm), -0.20)
        self.assertLess(S.prior_trend(safx), -0.20)
        self.assertGreater(S.prior_trend([0.5, 0.52, 0.49, 0.51, 0.5, 0.5]), -0.20)  # flat: still a swan
        self.assertIsNone(S.prior_trend([0.5, 0.4]))                                  # too little history
        self.assertIsNone(S.prior_trend(None))

    def test_falling_stock_is_crash_not_swan(self):
        with tempfile.TemporaryDirectory() as d:
            sc, http, st = make_scanner(None, d)
            sc.load_universe()
            orig = sc.daily_stats

            def falling(sym, now):
                out = dict(orig(sym, now))
                if sym == "DOWN":
                    out["closes"] = [1.6, 1.5, 1.4, 1.3, 1.2, 1.1, 1.0, 0.95, 0.9, 0.8]
                return out
            sc.daily_stats = falling
            got = {(a.kind, a.symbol): a for a in sc.cycle()}
            crash = got.get(("CRASH", "DOWN"))
            self.assertIsNotNone(crash)
            self.assertIn("Continuing downtrend", " ".join(crash.lines))
            # the bankruptcy 8-K is real news: that black swan still fires
            self.assertIn(("BLACKSWAN", "DOWN"), got)

class TestUpsideOnly(unittest.TestCase):
    """UPSIDE_ONLY (the live default): only PARABOLIC / BLACK SWAN moves UP, graded multibagger or
    day trade, each with a buy zone, stop and targets. Nothing for falling stocks."""

    def make(self, d, http=None):
        sc, http, st = make_scanner(http, d)
        sc.cfg.upside_only, sc.cfg.exit_alerts = True, False
        sc.load_universe()
        return sc, http, st

    def test_only_upside_alerts_with_a_plan(self):
        with tempfile.TemporaryDirectory() as d:
            sc, http, st = self.make(d)
            alerts = sc.cycle()
            kinds = {(a.kind, a.symbol) for a in alerts}
            self.assertTrue(kinds, "expected an upside alert")
            for k, sym in kinds:
                self.assertIn(k, ("PARABOLIC", "BLACKSWAN"), (k, sym))
            self.assertNotIn("DOWN", {a.symbol for a in alerts})          # crash + bankruptcy: silent
            self.assertNotIn("FLAT", {a.symbol for a in alerts})          # halt + offering news: silent
            rokt = next(a for a in alerts if a.symbol == "ROKT")
            text = " ".join(rokt.lines)
            self.assertRegex(text, "Multibagger|Day trade")
            self.assertIn("Buy zone", text)
            self.assertIn("Stop", text)
            self.assertIn("Target 1", text)
            self.assertTrue(st.d["trades"]["ROKT"]["open"])               # tracked for STOP / TAKE PROFIT / SELL

    def test_illiquid_non_runner_is_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            sc, http, st = self.make(d)
            sc.cfg.runner_score = 101                                    # nothing counts as a multibagger
            sc.cfg.dt_min_dv15_regular = sc.cfg.dt_min_dv15_extended = 1e12   # and nothing is liquid enough
            sc.cfg.max_spread = 0.001                                    # spread is the fallback check
            self.assertEqual([a for a in sc.cycle() if a.kind in ("PARABOLIC", "BLACKSWAN")], [])

    def test_up_black_swan(self):
        with tempfile.TemporaryDirectory() as d:
            sc, http, st = self.make(d)
            orig = sc.daily_stats

            def calm(sym, now):
                out = dict(orig(sym, now))
                out["sigma"] = 0.02                                      # a quiet stock: today's jump is extreme
                return out
            sc.daily_stats = calm
            alerts = sc.cycle()
            swan = [a for a in alerts if a.kind == "BLACKSWAN"]
            self.assertTrue(swan)
            self.assertTrue(all(a.symbol != "DOWN" for a in swan))
            self.assertIn("Buy zone", " ".join(swan[0].lines))

