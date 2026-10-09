"use client";

import { useEffect, useState } from "react";
import { api, getToken, setToken, ApiError } from "@/lib/api";

type Me = {
  id: number;
  username: string;
  email: string;
  date_joined: string;
  profile: { display_timezone: string };
  token: string;
};

export function AuthPanel() {
  const [state, setState] = useState<
    | { mode: "logged-out"; token: string | null }
    | { mode: "logged-in"; user: Me; token: string }
  >({ mode: "logged-out", token: null });

  useEffect(() => {
    void (async () => {
      try {
        const me = await api<Me>("/api/auth/me/");
        setState({ mode: "logged-in", user: me, token: getToken() ?? "" });
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          setState({ mode: "logged-out", token: getToken() ?? null });
        } else {
          setState({ mode: "logged-out", token: null });
        }
      }
    })();
  }, []);

  if (state.mode === "logged-in") {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-800/60 px-3 py-1.5 text-xs text-zinc-300">
        <span className="font-medium text-zinc-100">{state.user.username}</span>
        <span className="text-zinc-500">| Timezone {state.user.profile.display_timezone} UTC</span>
        <button
          className="ml-auto text-zinc-400 transition hover:text-zinc-100"
          onClick={async () => {
            try {
              await api("/api/auth/logout/", { method: "POST" });
            } finally {
              setToken(null);
              setState({ mode: "logged-out", token: null });
            }
          }}
        >
          Log out
        </button>
      </div>
    );
  }

  return (
    <form
      className="flex gap-2 text-xs"
      onSubmit={async (e) => {
        e.preventDefault();
        const form = new FormData(e.currentTarget);
        const username = form.get("username") as string;
        const password = form.get("password") as string;
        const mode = form.get("mode") as "login" | "register";
        try {
          if (mode === "register") {
            await api("/api/auth/register/", {
              method: "POST",
              body: { username, email: `${username}@example.com`, password },
            });
          } else {
            await api("/api/auth/login/", {
              method: "POST",
              body: { username, password },
            });
          }
          const me = await api<Me>("/api/auth/me/");
          setToken(me.token);
          setState({ mode: "logged-in", user: me, token: me.token });
        } catch (err) {
          if (err instanceof Error) alert(err.message);
        }
      }}
    >
      <select name="mode" className="bg-zinc-800 border border-zinc-600 rounded px-2 py-1 text-xs">
        <option value="login">Log in</option>
        <option value="register">Register</option>
      </select>
      <input
        name="username"
        placeholder="Username"
        required
        className="bg-zinc-800 border border-zinc-600 rounded px-2 py-1 text-xs"
      />
      <input
        name="password"
        type="password"
        placeholder="Password"
        required
        className="bg-zinc-800 border border-zinc-600 rounded px-2 py-1 text-xs"
      />
      <button
        type="submit"
        className="rounded bg-cyan-600 px-3 py-1 text-xs font-medium text-white transition hover:bg-cyan-500"
      >
        {state.mode === "logged-out" ? "Continue" : "Switch account"}
      </button>
    </form>
  );
}
