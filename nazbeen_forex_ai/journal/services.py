"""Journal and mentor services."""

from __future__ import annotations

from typing import Any, Dict, List

from nazbeen_forex_ai.journal.models import JournalEntry, MentorMessage
from nazbeen_forex_ai.analysis.models import ScreenshotAnalysis


class JournalService:
    def save_entry(self, user, data: Dict[str, Any]) -> JournalEntry:
        return JournalEntry.objects.create(
            user=user,
            symbol=data.get("symbol"),
            timeframe=data.get("timeframe"),
            analysis_session_id=data.get("analysis_session_id"),
            scenario_decision=data.get("scenario_decision"),
            entry=data.get("entry"),
            sl=data.get("sl"),
            tp=data.get("tp"),
            rr=data.get("rr"),
            outcome=data.get("outcome", "PENDING"),
            pnl=data.get("pnl"),
            notes=data.get("notes", ""),
            tags=data.get("tags", []),
            metrics=data.get("metrics", {}),
        )

    def search(self, user, query: str | None = None) -> List[JournalEntry]:
        qs = JournalEntry.objects.filter(user=user)
        if query:
            qs = qs.filter(notes__icontains=query)
        return list(qs[:50])


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
