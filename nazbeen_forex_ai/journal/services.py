"""Journal and mentor services (Phase 11F).

The journal records the full MASTER_SPEC §3.H context for historical review and
performance reports. Two rules are enforced here, both from the audit (M-15 /
M-08):

* **No fabrication** — a spec field that was never recorded is stored as
  ``None``/``""``/``[]``/``{}`` and is reported as ``null`` by the performance
  aggregate; it is never silently defaulted to a plausible value.
* **Ownership** — every read/write is scoped to the requesting user.

Input is validated eagerly so malformed payloads raise
``django.core.exceptions.ValidationError`` and the API answers **400**, matching
the pattern in ``risk/views.py`` (audit M-05).
"""

from __future__ import annotations

import csv
import io
import math
import uuid
from typing import Any, Dict, List, Optional

from django.core.exceptions import ValidationError
from django.utils import timezone

from nazbeen_forex_ai.analysis.models import ScreenshotAnalysis
from nazbeen_forex_ai.journal.models import JournalEntry, MentorMessage

# Text fields whose model column is nullable.
_NULLABLE_TEXT = ("symbol", "timeframe", "scenario_decision")
# Text fields whose model column is non-null (blank allowed).
_BLANK_TEXT = ("model_version", "strategy_version")
_NUMERIC_FIELDS = ("entry", "sl", "tp", "rr", "pnl", "estimated_probability")
_JSON_FIELDS = (
    ("tags", list),
    ("metrics", dict),
    ("market_snapshot", dict),
    ("detected_structures", dict),
)

_OUTCOMES = tuple(choice for choice, _ in JournalEntry.OUTCOME_CHOICES)
_SOURCES = tuple(choice for choice, _ in JournalEntry.SOURCE_CHOICES)

# CSV/JSON export column order.
EXPORT_FIELDS = (
    "id",
    "created_at",
    "symbol",
    "timeframe",
    "source",
    "source_ref",
    "analysis_timestamp",
    "scenario_decision",
    "entry",
    "sl",
    "tp",
    "rr",
    "estimated_probability",
    "outcome",
    "pnl",
    "model_version",
    "strategy_version",
    "notes",
    "tags",
)


def _as_float(value: Any, field: str) -> Optional[float]:
    """Coerce to a finite float, or ``None`` when the value is absent."""
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} must be a number")
    if not math.isfinite(number):
        raise ValidationError(f"{field} must be a finite number")
    return number


def _as_json(value: Any, field: str, expected: type) -> Any:
    if value is None:
        return None
    if not isinstance(value, expected):
        kind = "list" if expected is list else "object"
        raise ValidationError(f"{field} must be a JSON {kind}")
    return value


def _parse_uuid(value: Any) -> Optional[uuid.UUID]:
    if not value:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _analysis_context(analysis: ScreenshotAnalysis) -> Dict[str, Any]:
    """Derive spec §3.H context from a stored analysis (recorded data only)."""
    structured = analysis.structured_output or {}
    metadata = analysis.metadata or {}
    snapshot = {
        "symbol": analysis.symbol,
        "timeframe": analysis.timeframe,
        "source": structured.get("source"),
        "data_synchronized": structured.get("data_synchronized"),
        "uses_mtf_data": structured.get("uses_mtf_data"),
        "analysis_timestamp": structured.get("analysis_timestamp"),
    }
    signals = structured.get("deterministic_signals")
    return {
        "symbol": analysis.symbol,
        "timeframe": analysis.timeframe,
        "analysis_timestamp": analysis.created_at,
        "market_snapshot": snapshot,
        "detected_structures": signals if isinstance(signals, dict) else {},
        "model_version": structured.get("model") or metadata.get("model") or "",
    }


class JournalService:
    # ------------------------------------------------------------------ read
    def get_entry(self, user, entry_id: Any) -> Optional[JournalEntry]:
        """Return the user's entry, or ``None`` if it does not exist / not theirs."""
        ref = _parse_uuid(entry_id)
        if ref is None:
            return None
        return JournalEntry.objects.filter(user=user, id=ref).first()

    def search(
        self,
        user,
        query: str | None = None,
        symbol: str | None = None,
        outcome: str | None = None,
        source: str | None = None,
        limit: int = 50,
    ) -> List[JournalEntry]:
        qs = JournalEntry.objects.filter(user=user)
        if query:
            qs = qs.filter(notes__icontains=query)
        if symbol:
            qs = qs.filter(symbol__iexact=symbol)
        if outcome:
            qs = qs.filter(outcome=outcome)
        if source:
            qs = qs.filter(source=source)
        return list(qs[: max(1, min(int(limit), 200))])

    def list_entries(self, user) -> List[JournalEntry]:
        return self.search(user)

    # ------------------------------------------------------------- validation
    def _resolve_analysis(self, user, data: Dict[str, Any]) -> Optional[ScreenshotAnalysis]:
        raw = data.get("screenshot_analysis_id") or data.get("analysis_session_id")
        ref = _parse_uuid(raw)
        if ref is None:
            return None
        return ScreenshotAnalysis.objects.filter(user=user, id=ref).first()

    @staticmethod
    def _parse_dt(value: Any):
        if not value:
            return None
        if hasattr(value, "isoformat"):
            return value
        from django.utils.dateparse import parse_datetime

        parsed = parse_datetime(str(value))
        if parsed is None:
            raise ValidationError("analysis_timestamp must be an ISO-8601 timestamp")
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone=timezone.utc)
        return parsed

    def _validated_fields(self, user, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and return only the fields the caller supplied (plus any
        context derived from a linked analysis)."""
        if not isinstance(data, dict):
            raise ValidationError("journal entry must be an object")

        fields: Dict[str, Any] = {}

        if "outcome" in data:
            outcome = data.get("outcome") or "PENDING"
            if outcome not in _OUTCOMES:
                raise ValidationError("outcome must be one of " + ", ".join(_OUTCOMES))
            fields["outcome"] = outcome

        if "source" in data:
            source = data.get("source") or "manual"
            if source not in _SOURCES:
                raise ValidationError("source must be one of " + ", ".join(_SOURCES))
            fields["source"] = source

        if "source_ref" in data:
            fields["source_ref"] = data.get("source_ref") or ""

        for name in _NULLABLE_TEXT:
            if name in data:
                value = data.get(name)
                fields[name] = None if value in (None, "") else str(value)

        for name in _BLANK_TEXT:
            if name in data:
                fields[name] = data.get(name) or ""

        for name in _NUMERIC_FIELDS:
            if name in data:
                fields[name] = _as_float(data.get(name), name)

        for name, expected in _JSON_FIELDS:
            if name in data:
                value = _as_json(data.get(name), name, expected)
                fields[name] = ([] if expected is list else {}) if value is None else value

        if "notes" in data:
            fields["notes"] = data.get("notes") or ""

        if "analysis_timestamp" in data:
            fields["analysis_timestamp"] = self._parse_dt(data.get("analysis_timestamp"))

        if "screenshot_analysis_id" in data or "analysis_session_id" in data:
            analysis = self._resolve_analysis(user, data)
            fields["screenshot_analysis"] = analysis
            if analysis is not None:
                if not data.get("analysis_session_id"):
                    fields["analysis_session_id"] = analysis.id
                for name, value in _analysis_context(analysis).items():
                    if name not in data:
                        fields[name] = value
            else:
                fields["analysis_session_id"] = _parse_uuid(data.get("analysis_session_id"))

        # A linked analysis implies screenshot_analysis origin unless stated.
        if fields.get("screenshot_analysis") is not None and "source" not in data:
            fields["source"] = "screenshot_analysis"

        return fields

    def _create_defaults(self) -> Dict[str, Any]:
        return {
            "symbol": None,
            "timeframe": None,
            "source": "manual",
            "source_ref": "",
            "scenario_decision": None,
            "model_version": "",
            "strategy_version": "",
            "notes": "",
            "outcome": "PENDING",
            "tags": [],
            "metrics": {},
            "market_snapshot": {},
            "detected_structures": {},
            "analysis_timestamp": None,
            "analysis_session_id": None,
            "screenshot_analysis": None,
            **{name: None for name in _NUMERIC_FIELDS},
        }

    # ----------------------------------------------------------------- write
    def save_entry(self, user, data: Dict[str, Any]) -> JournalEntry:
        fields = self._create_defaults()
        fields.update(self._validated_fields(user, data))
        return JournalEntry.objects.create(user=user, **fields)

    def update_entry(self, user, entry_id: Any, data: Dict[str, Any]) -> Optional[JournalEntry]:
        entry = self.get_entry(user, entry_id)
        if entry is None:
            return None
        for name, value in self._validated_fields(user, data).items():
            setattr(entry, name, value)
        entry.save()
        entry.refresh_from_db()
        return entry

    def delete_entry(self, user, entry_id: Any) -> bool:
        entry = self.get_entry(user, entry_id)
        if entry is None:
            return False
        entry.delete()
        return True

    # ------------------------------------------------------------- analytics
    def performance(self, user) -> Dict[str, Any]:
        """Honest performance aggregate over recorded fields only.

        Every ratio/statistic is ``None`` when the data needed to compute it was
        never recorded; the payload always reports the sample sizes used.
        """
        entries = list(JournalEntry.objects.filter(user=user))

        counts = {name: 0 for name in _OUTCOMES}
        for entry in entries:
            if entry.outcome in counts:
                counts[entry.outcome] += 1
        closed = counts["WIN"] + counts["LOSS"] + counts["BE"]
        decided = counts["WIN"] + counts["LOSS"]
        win_rate = (counts["WIN"] / decided) if decided else None

        rrs = [float(e.rr) for e in entries if e.rr is not None]
        average_rr = (sum(rrs) / len(rrs)) if rrs else None

        pnl_series = sorted(
            ((e.created_at, float(e.pnl)) for e in entries if e.pnl is not None),
            key=lambda pair: pair[0],
        )
        total_pnl = sum(value for _, value in pnl_series) if pnl_series else None
        expectancy = (total_pnl / len(pnl_series)) if pnl_series else None

        gains = sum(value for _, value in pnl_series if value > 0)
        losses = sum(value for _, value in pnl_series if value < 0)
        profit_factor = (gains / abs(losses)) if losses < 0 else None

        max_drawdown = None
        if pnl_series:
            peak = cum = dd = 0.0
            for _, value in pnl_series:
                cum += value
                peak = max(peak, cum)
                dd = max(dd, peak - cum)
            max_drawdown = dd

        return {
            "total_entries": len(entries),
            "outcomes": counts,
            "closed": closed,
            "open": counts["PENDING"],
            "win_rate": win_rate,
            "average_rr": average_rr,
            "total_pnl": total_pnl,
            "expectancy": expectancy,
            "profit_factor": profit_factor,
            "max_drawdown": max_drawdown,
            "pnl_sample": len(pnl_series),
            "rr_sample": len(rrs),
            "note": (
                "Computed only from recorded journal fields. null means the data "
                "required for that statistic was not recorded."
            ),
        }

    # ---------------------------------------------------------------- export
    def export(self, user, fmt: str = "json"):
        """Return ``(content_type, payload)`` for ``fmt`` in {json, csv}."""
        fmt = (fmt or "json").lower()
        if fmt not in ("json", "csv"):
            raise ValidationError("format must be 'json' or 'csv'")

        entries = list(JournalEntry.objects.filter(user=user))
        rows = [self._export_row(entry) for entry in entries]

        if fmt == "csv":
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=list(EXPORT_FIELDS))
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key) for key in EXPORT_FIELDS})
            return "text/csv; charset=utf-8", buffer.getvalue()

        return "application/json", {"count": len(rows), "entries": rows}

    @staticmethod
    def _export_row(entry: JournalEntry) -> Dict[str, Any]:
        def iso(value):
            return value.isoformat().replace("+00:00", "Z") if value else None

        return {
            "id": str(entry.id),
            "created_at": iso(entry.created_at),
            "symbol": entry.symbol,
            "timeframe": entry.timeframe,
            "source": entry.source,
            "source_ref": entry.source_ref,
            "analysis_timestamp": iso(entry.analysis_timestamp),
            "scenario_decision": entry.scenario_decision,
            "entry": entry.entry,
            "sl": entry.sl,
            "tp": entry.tp,
            "rr": entry.rr,
            "estimated_probability": entry.estimated_probability,
            "outcome": entry.outcome,
            "pnl": entry.pnl,
            "model_version": entry.model_version,
            "strategy_version": entry.strategy_version,
            "notes": entry.notes,
            "tags": entry.tags,
        }


class MentorService:
    def answer(self, user, question: str, context: Dict[str, Any] | None = None) -> str:
        context = context or {}
        # save user message
        MentorMessage.objects.create(user=user, role="user", content=question, context_summary=context)
        # basic context-aware explanation
        analyses = ScreenshotAnalysis.objects.filter(user=user).order_by("-created_at")[:5]
        evidence = []
        for a in analyses:
            so = a.structured_output or {}
            evidence.append(so.get("summary", ""))
        answer = (
            "Mentor (analysis-only): I can explain why setups qualify/fail using your saved analyses. "
            "Deterministic structure is authoritative. Never fabricate outcomes. "
            f"Recent summaries: {evidence[:2]}. "
            "Focus on evidence, reject unverified claims, and prefer WAIT when uncertain."
        )
        MentorMessage.objects.create(user=user, role="assistant", content=answer, context_summary=context)
        return answer
