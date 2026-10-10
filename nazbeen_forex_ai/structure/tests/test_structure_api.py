"""Structure API tests (Phase 11D).

Covers the dashboard's data contract: detected BOS/CHOCH/MSS events, FVG and
order-block zones, and liquidity levels must be served by the deterministic
engine with timestamps that align to the exact candles they were computed
from, and the multi-timeframe section must carry the real biases + conflicts
(but a timeframe whose data cannot be fetched is ``null`` — never a made-up
NEUTRAL).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from nazbeen_forex_ai.marketdata.mock import MockMarketDataProvider
from nazbeen_forex_ai.marketdata.providers import Candle, MarketDataProviderError

# --- Fixtures shared with the mtf_bias unit tests (biases proven there) -----

def _c(i: int, o: float, h: float, l: float, cl: float) -> dict:
    return {
        "time": f"2026-01-01T00:{i:02d}:00+00:00",
        "open": o,
        "high": h,
        "low": l,
        "close": cl,
        "volume": 10,
    }


_RISING = [
    _c(0, 1.1000, 1.1010, 1.0990, 1.1005),
    _c(1, 1.1005, 1.1020, 1.1000, 1.1015),
    _c(2, 1.1015, 1.1005, 1.0985, 1.0990),
    _c(3, 1.0990, 1.0995, 1.0975, 1.0980),
    _c(4, 1.0980, 1.1030, 1.0990, 1.1025),
    _c(5, 1.1025, 1.1060, 1.1020, 1.1055),
    _c(6, 1.1055, 1.1075, 1.1040, 1.1070),
    _c(7, 1.1070, 1.1055, 1.1030, 1.1035),
    _c(8, 1.1035, 1.1045, 1.1025, 1.1040),
    _c(9, 1.1040, 1.1085, 1.1060, 1.1080),
]


def _mirror(candles: list[dict]) -> list[dict]:
    return [
        {
            **c,
            "open": round(2.2070 - c["open"], 6),
            "close": round(2.2070 - c["close"], 6),
            "high": round(2.2070 - c["low"], 6),
            "low": round(2.2070 - c["high"], 6),
        }
        for c in candles
    ]


_FALLING = _mirror(_RISING)


def _zigzag() -> list[dict]:
    """Rally → pullback → structure break with a genuine 3-candle FVG, a
    displacement bar (order block) and an equal-high pair (liquidity)."""
    t0 = datetime(2026, 10, 7, 0, 0, tzinfo=timezone.utc)

    def bar(i: int, o: float, c: float) -> dict:
        return {
            "time": (t0 + timedelta(minutes=15 * i)).isoformat().replace("+00:00", "Z"),
            "open": round(o, 6),
            "high": round(max(o, c) + 0.0002, 6),
            "low": round(min(o, c) - 0.0002, 6),
            "close": round(c, 6),
        }

    out: list[dict] = []
    for i in range(10):  # leg 1: rally
        o = 1.1000 + 0.0004 * i
        out.append(bar(i, o, o + 0.0004))
    for i in range(10, 20):  # leg 2: pullback
        o = 1.1036 - 0.0005 * (i - 10)
        out.append(bar(i, o, o - 0.0005))
    for i in range(20, 34):  # leg 3: rally through the prior high
        o = 1.0986 + 0.0006 * (i - 20)
        out.append(bar(i, o, o + 0.0006))
    # Crafted impulse: c1.high (1.1004) < c3.low (1.1044) → bullish FVG.
    out[20] = bar(20, 1.1000, 1.1002)
    out[21] = bar(21, 1.1010, 1.1040)  # displacement body 0.0030
    out[22] = bar(22, 1.1046, 1.1050)
    # Equal highs → liquidity (buy-side) on bars 5 and 6.
    out[5]["high"] = out[6]["high"] = 1.1045
    return out


class _SyntheticProvider(MockMarketDataProvider):
    """Mock provider serving fixed candle fixtures (no wall-clock drift).

    ``fail`` lists timeframes that raise, simulating an unavailable timeframe.
    """

    def __init__(self, data: dict[str, list[dict]], fail: tuple[str, ...] = ()) -> None:
        super().__init__()
        self._data = data
        self._fail = set(fail)

    def get_candles(self, symbol, timeframe, start=None, count=None):  # noqa: ANN001
        if not self._connected:
            raise MarketDataProviderError("not connected")
        if timeframe in self._fail:
            raise MarketDataProviderError(f"no data for {timeframe}")
        raw = self._data.get(timeframe)
        if raw is None:
            raise MarketDataProviderError(f"unknown {timeframe}")
        selected = raw[-count:] if count else raw
        return [
            Candle(
                time=datetime.fromisoformat(c["time"].replace("Z", "+00:00")),
                open=c["open"],
                high=c["high"],
                low=c["low"],
                close=c["close"],
                tick_volume=10,
            )
            for c in selected
        ]


class _DeadProvider(MockMarketDataProvider):
    def connect(self) -> bool:
        raise MarketDataProviderError("SECRET-DETAIL-CONNECTION-STRING-XYZ")


@pytest.fixture
def api() -> APIClient:
    client = APIClient()
    user = get_user_model().objects.create_user("struct1", password="Struct-2026!")
    client.force_authenticate(user=user)
    return client


def _url() -> str:
    return reverse("structure:structure")


def _norm(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


@pytest.mark.django_db
def test_structure_requires_authentication() -> None:
    resp = APIClient().get(_url())
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "query",
    [
        "?symbol=EURUSD&timeframe=M30",
        "?symbol=EURUSD&timeframe=M15&count=0",
        "?symbol=EURUSD&timeframe=M15&count=abc",
        "?symbol=EUR;DROP&timeframe=M15",
    ],
)
def test_invalid_structure_params_return_400(api: APIClient, query: str) -> None:
    resp = api.get(_url() + query)
    assert resp.status_code == 400
    assert resp.json()["error"] == "Invalid request"


@pytest.mark.django_db
def test_structure_happy_path_shapes(api: APIClient) -> None:
    resp = api.get(_url() + "?symbol=EURUSD&timeframe=M15&count=100")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "EURUSD"
    assert body["timeframe"] == "M15"
    # Test settings force the mock provider — and it must be labeled.
    assert body["data_source"] == "mock"
    assert body["market_state"] in ("open", "closed")
    assert isinstance(body["stale"], bool)
    assert body["last_bar_age_sec"] is None or isinstance(
        body["last_bar_age_sec"], (int, float)
    )
    assert isinstance(body["threshold_sec"], int)
    assert set(body["mtf"]) == {"H1", "M15", "M5", "M1", "conflicts"}
    for tf in ("H1", "M15", "M5", "M1"):
        assert body["mtf"][tf] in ("BULLISH", "BEARISH", "NEUTRAL")
    assert isinstance(body["mtf"]["conflicts"], list)
    for key in ("swings", "events", "fvgs", "order_blocks", "liquidity"):
        assert isinstance(body[key], list)


@pytest.mark.django_db
def test_detects_real_events_and_maps_them_to_candles(api: APIClient, monkeypatch) -> None:
    from nazbeen_forex_ai.structure import views as st_views

    data = {"M15": _zigzag(), "H1": _zigzag(), "M5": _zigzag(), "M1": _zigzag()}
    monkeypatch.setattr(st_views, "get_market_data_provider", lambda: _SyntheticProvider(data))

    resp = api.get(_url() + "?symbol=EURUSD&timeframe=M15&count=34")
    assert resp.status_code == 200
    body = resp.json()

    # The fixture provably produces a BOS, a bullish FVG, an order block and
    # an equal-high liquidity level (engine-drawn, not asserted by hand).
    assert any(e["type"] == "BOS" and e["direction"] == "bullish" for e in body["events"])
    assert any(f["direction"] == "bullish" for f in body["fvgs"])
    assert any(o["type"] == "ORDERBLOCK" for o in body["order_blocks"])
    assert any(l["details"].get("kind") == "equal_high" for l in body["liquidity"])
    assert body["swings"], "swing classification must not be empty on this fixture"

    # --- Timestamp alignment: every marker references an exact candle time ---
    candle_times = {_norm(c["time"]) for c in data["M15"]}
    for e in body["events"]:
        assert _norm(e["confirmed_at"]) in candle_times, "event off candle grid"
        assert _norm(e["end_time"]) in candle_times
        assert _norm(e["formation_time"]) in candle_times
    for f in body["fvgs"]:
        assert _norm(f["start_time"]) in candle_times
        assert _norm(f["end_time"]) in candle_times
    for o in body["order_blocks"]:
        assert _norm(o["formation_time"]) in candle_times
        assert _norm(o["confirmed_at"]) in candle_times
    for lq in body["liquidity"]:
        # index-only events get the exact candle time attached by the view
        assert _norm(lq["time"]) in candle_times
    for s in body["swings"]:
        assert _norm(s["swing"]["time"]) in candle_times

    # Zone prices must be real candle prices, never interpolated.
    all_prices = {
        round(p, 6)
        for c in data["M15"]
        for p in (c["open"], c["high"], c["low"], c["close"])
    }
    liq = next(l for l in body["liquidity"] if l["details"].get("kind") == "equal_high")
    assert round(liq["level"], 6) in all_prices


@pytest.mark.django_db
def test_mtf_section_reports_real_biases_and_conflicts(api: APIClient, monkeypatch) -> None:
    from nazbeen_forex_ai.structure import views as st_views

    data = {"H1": _RISING, "M15": _RISING, "M5": _FALLING, "M1": _FALLING}
    monkeypatch.setattr(st_views, "get_market_data_provider", lambda: _SyntheticProvider(data))

    resp = api.get(_url() + "?symbol=EURUSD&timeframe=M15&count=10")
    assert resp.status_code == 200
    mtf = resp.json()["mtf"]
    assert mtf["H1"] == "BULLISH"
    assert mtf["M15"] == "BULLISH"
    assert mtf["M5"] == "BEARISH"
    assert mtf["M1"] == "BEARISH"
    # Every disagreeing decisive pair must be reported (audit H-05).
    assert "H1 BULLISH vs M5 BEARISH" in mtf["conflicts"]
    assert "H1 BULLISH vs M1 BEARISH" in mtf["conflicts"]
    assert "M15 BULLISH vs M5 BEARISH" in mtf["conflicts"]
    assert "M15 BULLISH vs M1 BEARISH" in mtf["conflicts"]


@pytest.mark.django_db
def test_unavailable_timeframe_is_null_not_neutral(api: APIClient, monkeypatch) -> None:
    from nazbeen_forex_ai.structure import views as st_views

    data = {"M15": _RISING, "M5": _FALLING, "M1": _FALLING}  # H1 missing
    monkeypatch.setattr(
        st_views, "get_market_data_provider", lambda: _SyntheticProvider(data, fail=("H1",))
    )

    resp = api.get(_url() + "?symbol=EURUSD&timeframe=M15&count=10")
    assert resp.status_code == 200
    mtf = resp.json()["mtf"]
    assert mtf["H1"] is None, "an unfetchable timeframe is unavailable, not NEUTRAL"
    assert mtf["M15"] == "BULLISH"
    assert mtf["M5"] == "BEARISH"
    # Conflicts still reflect only timeframes that actually had data.
    assert "M15 BULLISH vs M5 BEARISH" in mtf["conflicts"]


@pytest.mark.django_db
def test_provider_failure_is_generic_503(api: APIClient, monkeypatch) -> None:
    from nazbeen_forex_ai.structure import views as st_views

    monkeypatch.setattr(st_views, "get_market_data_provider", lambda: _DeadProvider())
    resp = api.get(_url() + "?symbol=EURUSD&timeframe=M15&count=10")
    assert resp.status_code == 503
    body = resp.content.decode()
    assert "SECRET-DETAIL" not in body
    from nazbeen_forex_ai.marketdata.views import GENERIC_PROVIDER_ERROR

    assert resp.json()["error"] == GENERIC_PROVIDER_ERROR


@pytest.mark.django_db
def test_missing_primary_candles_is_503(api: APIClient, monkeypatch) -> None:
    from nazbeen_forex_ai.structure import views as st_views

    monkeypatch.setattr(
        st_views, "get_market_data_provider", lambda: _SyntheticProvider({})
    )
    resp = api.get(_url() + "?symbol=EURUSD&timeframe=M15&count=10")
    assert resp.status_code == 503
