"use client";

import { Fragment, useEffect, useState } from "react";
import { apiRequest, clearToken, getToken, isAuthError, setToken as saveToken } from "@/lib/api";
import { AvailabilityPanel } from "@/components/AvailabilityPanel";
import type { AvailabilityState } from "@/types/railway";
import { BOOKABLE_CLASSES, className, trainClasses } from "@/lib/travelClasses";

type RowAvailability = AvailabilityState & { travelClass: string };

const MIN_PASSWORD_LENGTH = 10;

/** Today's date in the browser's local time as YYYY-MM-DD (the <input type="date"> format). */
function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** YYYY-MM-DD -> DD-MM-YYYY, the format the backend and RailKit expect. */
function toRailDate(iso: string) {
  const [y, m, d] = iso.split("-");
  return `${d}-${m}-${y}`;
}

type Train = Record<string, unknown>;

export default function Home() {
  const [mode, setMode] = useState<"login" | "register">("register");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [from, setFrom] = useState("NDLS");
  const [to, setTo] = useState("BCT");
  // `date` is the picker value (YYYY-MM-DD). `searchedDate` is the DD-MM-YYYY
  // date the current results were fetched for: search only returns trains that
  // run on that date, so availability must use it even if the picker changes.
  const [date, setDate] = useState(todayISO);
  const [searchedDate, setSearchedDate] = useState("");
  // Availability per result row, keyed by trainKey(); shown in a row under the train.
  const [avail, setAvail] = useState<Record<string, RowAvailability>>({});
  // Fallback class choice for trains whose search result lists no classes.
  const [fallbackClass, setFallbackClass] = useState<Record<string, string>>({});
  const [trains, setTrains] = useState<Train[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [checkingSession, setCheckingSession] = useState(true);

  // Restore a saved session on page load, verifying the token with the backend.
  useEffect(() => {
    const saved = getToken();
    if (!saved) { setCheckingSession(false); return; }
    apiRequest("/auth/me")
      .then((user) => { setToken(saved); setMessage(`Signed in as ${user.email}`); })
      .catch((error) => {
        if (isAuthError(error)) { clearToken(); setMessage("Your session has expired. Please log in again."); }
        else setMessage(error instanceof Error ? error.message : "Could not verify your session");
      })
      .finally(() => setCheckingSession(false));
  }, []);

  function endSession(text: string) {
    clearToken();
    setToken(null); setTrains([]); setAvail({}); setMessage(text);
  }

  // A 401 on a protected call means the token is missing, invalid or expired.
  function handleError(error: unknown, fallback: string) {
    if (isAuthError(error)) { endSession("Your session has expired. Please log in again."); return; }
    setMessage(error instanceof Error ? error.message : fallback);
  }

  async function authenticate() {
    setMessage("");
    if (!email.trim()) { setMessage("Enter your email address."); return; }
    if (mode === "register" && password.length < MIN_PASSWORD_LENGTH) {
      setMessage(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`); return;
    }
    if (!password) { setMessage("Enter your password."); return; }
    setBusy(true);
    try {
      const result = await apiRequest(`/auth/${mode}`, {
        method: "POST", body: JSON.stringify({ email: email.trim(), password })
      });
      saveToken(result.access_token);
      setToken(result.access_token);
      setPassword("");
      setMessage(`Signed in as ${result.user.email}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Authentication failed");
    } finally { setBusy(false); }
  }

  async function search() {
    if (!date) { setMessage("Choose a journey date."); return; }
    if (date < todayISO()) { setMessage("Journey date is in the past. Choose today or a later date."); return; }
    const journeyDate = toRailDate(date);
    setBusy(true); setMessage(""); setTrains([]); setSearchedDate(""); setAvail({});
    try {
      const result = await apiRequest(
        `/railway/trains/between?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&date=${encodeURIComponent(journeyDate)}`
      );
      setTrains(result.data ?? []);
      setSearchedDate(journeyDate);
      setMessage(`${(result.data ?? []).length} train(s) returned`);
    } catch (error) {
      handleError(error, "Train search failed");
    } finally { setBusy(false); }
  }

  async function availability(train: Train, travelClass: string) {
    const trainNo = String(train.train_no ?? train.trainNo ?? "");
    if (!trainNo) { setMessage("Train number was not present in the provider response."); return; }
    // Search returns trains from nearby stations too (e.g. NZM for NDLS), so
    // availability must use the train's own boarding/alighting stations.
    const segFrom = String(train.from_stn_code ?? "");
    const segTo = String(train.to_stn_code ?? "");
    if (!segFrom || !segTo) { setMessage("Station codes were not present in the provider response."); return; }
    const key = trainKey(train);
    const current = avail[key];
    if (current?.state === "loading") return;
    // Clicking the class that is already shown hides the panel.
    if (current && current.travelClass === travelClass) {
      setAvail(({ [key]: _removed, ...rest }) => rest);
      return;
    }
    setAvail(prev => ({ ...prev, [key]: { state: "loading", travelClass } }));
    try {
      const result = await apiRequest(
        `/railway/availability/${trainNo}?from=${encodeURIComponent(segFrom)}&to=${encodeURIComponent(segTo)}&date=${encodeURIComponent(searchedDate)}&travel_class=${encodeURIComponent(travelClass)}&quota=GN`
      );
      if (!result?.data) throw new Error("RailKit returned an availability response without data.");
      setAvail(prev => ({ ...prev, [key]: { state: "done", data: result.data, fetchedAt: new Date(), travelClass } }));
    } catch (error) {
      if (isAuthError(error)) { handleError(error, ""); return; }
      const text = error instanceof Error ? error.message : "Availability check failed";
      setAvail(prev => ({ ...prev, [key]: { state: "error", message: text, travelClass } }));
    }
  }

  function trainKey(train: Train) {
    return `${String(train.train_no ?? "")}-${String(train.from_stn_code ?? "")}-${String(train.to_stn_code ?? "")}`;
  }

  function logout() {
    endSession("Signed out");
  }

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-5 py-10">
      <header className="mb-10 flex items-center justify-between">
        <div><p className="text-sm font-semibold text-blue-700">RAILWAY ASSISTANT</p><h1 className="mt-1 text-3xl font-semibold">Journey search</h1><p className="mt-2 text-sm text-slate-500">Search trains and inspect segment availability.</p></div>
        {token && <button onClick={logout} className="rounded-lg border bg-white px-4 py-2 text-sm">Sign out</button>}
      </header>

      {checkingSession ? (
        <p className="text-sm text-slate-500" role="status">Checking your session…</p>
      ) : !token ? (
        <section className="max-w-md rounded-2xl border bg-white p-6 shadow-sm">
          <div className="mb-5 flex gap-2">
            <button onClick={() => setMode("register")} className={`rounded-lg px-3 py-2 text-sm ${mode === "register" ? "bg-slate-900 text-white" : "bg-slate-100"}`}>Create account</button>
            <button onClick={() => setMode("login")} className={`rounded-lg px-3 py-2 text-sm ${mode === "login" ? "bg-slate-900 text-white" : "bg-slate-100"}`}>Log in</button>
          </div>
          <label className="mb-1 block text-sm">Email</label>
          <input className="mb-4 w-full rounded-lg border p-3" type="email" value={email} onChange={e => setEmail(e.target.value)} />
          <label className="mb-1 block text-sm">Password (minimum 10 characters)</label>
          <input className="mb-5 w-full rounded-lg border p-3" type="password" value={password} onChange={e => setPassword(e.target.value)} />
          <button disabled={busy} onClick={authenticate} className="w-full rounded-lg bg-slate-900 p-3 text-white disabled:opacity-50">{busy ? "Please wait…" : mode === "register" ? "Create account" : "Log in"}</button>
        </section>
      ) : (
        <section className="rounded-2xl border bg-white p-6 shadow-sm">
          <h2 className="mb-5 text-lg font-semibold">Find trains between stations</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="From station code" value={from} onChange={setFrom} />
            <Field label="To station code" value={to} onChange={setTo} />
            <label className="block text-sm">Journey date<input type="date" min={todayISO()} value={date} onChange={e => setDate(e.target.value)} className="mt-1 w-full rounded-lg border p-3" /></label>
            <div className="flex items-end"><button disabled={busy} onClick={search} className="w-full rounded-lg bg-slate-900 p-3 text-white disabled:opacity-50">{busy ? "Searching…" : "Search trains"}</button></div>
          </div>
          <p className="mt-3 text-xs text-slate-500">Use station codes such as NDLS, JP, CUR, AII or HYB.</p>
          {trains.length > 0 && <div className="mt-8 overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b text-slate-500"><th className="p-3">Train</th><th className="p-3">From → To</th><th className="p-3">Departure</th><th className="p-3">Arrival</th><th className="p-3">Duration</th><th className="p-3">Check availability</th></tr></thead><tbody>{trains.map((train, i) => { const a = avail[trainKey(train)]; return <Fragment key={`${trainKey(train)}-${i}`}><tr className={a ? "" : "border-b"}><td className="p-3"><b>{String(train.train_no ?? "")}</b><br />{String(train.train_name ?? "")}</td><td className="p-3" title={`${String(train.from_stn_name ?? "")} → ${String(train.to_stn_name ?? "")}`}>{String(train.from_stn_code ?? "—")} → {String(train.to_stn_code ?? "—")}</td><td className="p-3">{String(train.from_time ?? "—")}</td><td className="p-3">{String(train.to_time ?? "—")}</td><td className="p-3">{String(train.travel_time ?? "—")}</td><td className="p-3"><ClassPicker train={train} active={a} fallback={fallbackClass[trainKey(train)] ?? "3A"} onFallbackChange={c => setFallbackClass(prev => ({ ...prev, [trainKey(train)]: c }))} onPick={c => availability(train, c)} /></td></tr>{a && <tr className="border-b bg-slate-50"><td colSpan={6} className="px-3 pb-4 pt-1"><AvailabilityPanel result={a} searchedDate={searchedDate} /></td></tr>}</Fragment>; })}</tbody></table></div>}
        </section>
      )}
      {message && <pre className="mt-5 overflow-x-auto whitespace-pre-wrap rounded-xl border bg-white p-4 text-sm text-slate-700">{message}</pre>}
      <p className="mt-8 text-xs text-slate-400">Availability is provider-supplied and can change. Verify on official railway channels before booking.</p>
    </main>
  );
}

function ClassPicker({ train, active, fallback, onFallbackChange, onPick }: {
  train: Train;
  active?: RowAvailability;
  fallback: string;
  onFallbackChange: (travelClass: string) => void;
  onPick: (travelClass: string) => void;
}) {
  const classes = trainClasses(train.classes_of_travel);
  const loading = active?.state === "loading";

  // RailKit did not list classes for this train: let the user choose any bookable class.
  if (classes.length === 0) {
    const shown = active?.travelClass === fallback;
    return (
      <div className="flex items-center gap-2">
        <select aria-label={`Class for train ${String(train.train_no ?? "")}`} value={fallback} onChange={e => onFallbackChange(e.target.value)} className="rounded-md border bg-white px-2 py-2">
          {BOOKABLE_CLASSES.map(c => <option key={c} value={c}>{c}{className(c) !== c ? ` · ${className(c)}` : ""}</option>)}
        </select>
        <button onClick={() => onPick(fallback)} disabled={loading} aria-expanded={shown} className="whitespace-nowrap rounded-md border px-3 py-2 disabled:opacity-50">
          {loading ? "Checking…" : shown ? "Hide" : "Check"}
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap gap-1.5" role="group" aria-label={`Classes for train ${String(train.train_no ?? "")}`}>
      {classes.map(c => {
        const selected = active?.travelClass === c;
        return (
          <button
            key={c}
            onClick={() => onPick(c)}
            disabled={loading}
            aria-pressed={selected}
            title={selected && !loading ? `Hide ${className(c)}` : `Check ${className(c)} availability`}
            className={`min-w-11 rounded-md border px-2.5 py-1.5 text-xs font-semibold disabled:opacity-50 ${selected ? "border-slate-900 bg-slate-900 text-white" : "bg-white hover:bg-slate-100"}`}
          >
            {selected && loading ? "…" : c}
          </button>
        );
      })}
    </div>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label className="block text-sm">{label}<input value={value} onChange={e => onChange(e.target.value)} className="mt-1 w-full rounded-lg border p-3" /></label>;
}
