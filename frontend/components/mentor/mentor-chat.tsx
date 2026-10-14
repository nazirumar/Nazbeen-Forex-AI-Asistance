"use client";

/**
 * AI mentor chat (Phase 11G §P2.5).
 *
 * Posts to `POST /api/mentor/ask/` (Phase 11F) and renders the returned
 * `answer` verbatim. The mentor is **analysis-only** — it explains setups from
 * saved analyses; it never places trades or states guaranteed outcomes. No
 * answer is ever fabricated client-side.
 */

import { useState } from "react";
import { api } from "@/lib/api";
import { ErrorState } from "@/components/ui/states";

interface MentorAnswer {
  answer: string;
}

interface Turn {
  role: "user" | "mentor";
  text: string;
}

export function MentorChat() {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const send = async () => {
    const q = question.trim();
    if (!q || sending) return;
    setTurns((prev) => [...prev, { role: "user", text: q }]);
    setQuestion("");
    setSending(true);
    setError(null);
    try {
      const res = await api<MentorAnswer>("/api/mentor/ask/", {
        method: "POST",
        body: { question: q },
      });
      setTurns((prev) => [...prev, { role: "mentor", text: res.answer }]);
    } catch (err) {
      setError(err);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="flex flex-col gap-4" data-testid="mentor-chat">
      <section className="rounded-2xl border border-zinc-800 bg-[#0c1118] p-4">
        <h2 className="text-sm font-semibold text-zinc-100">AI mentor</h2>
        <p className="mt-0.5 text-xs text-zinc-500">
          Analysis-only explanation of your saved setups. Never trade execution, never guaranteed
          outcomes.
        </p>

        <div className="mt-3 flex flex-col gap-2" data-testid="mentor-transcript">
          {turns.length === 0 ? (
            <p className="text-xs text-zinc-500" data-testid="mentor-empty">
              Ask a question about a setup, e.g. “Why did this become WAIT?”.
            </p>
          ) : (
            turns.map((turn, i) => (
              <div
                key={i}
                data-testid={`mentor-turn-${turn.role}`}
                className={`max-w-[85ch] rounded-xl px-3 py-2 text-sm ${
                  turn.role === "user"
                    ? "self-end bg-cyan-600/20 text-cyan-100"
                    : "self-start bg-zinc-900/70 text-zinc-200"
                }`}
              >
                {turn.text}
              </div>
            ))
          )}
          {sending ? (
            <p className="self-start text-xs text-zinc-500" data-testid="mentor-thinking">
              Thinking…
            </p>
          ) : null}
        </div>

        <form
          className="mt-3 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            void send();
          }}
        >
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask the mentor about a setup…"
            aria-label="Ask the mentor"
            data-testid="mentor-input"
            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 text-sm text-zinc-100 outline-none transition focus:border-cyan-600"
          />
          <button
            type="submit"
            disabled={sending || question.trim() === ""}
            data-testid="mentor-send"
            className="shrink-0 rounded-lg bg-cyan-600 px-3.5 py-1.5 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Send
          </button>
        </form>

        {error != null && (
          <div className="mt-3">
            <ErrorState error={error} label="Mentor unavailable" />
          </div>
        )}
      </section>
    </div>
  );
}
