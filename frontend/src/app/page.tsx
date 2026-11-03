"use client";

import { useState } from "react";
import { apiRequest } from "@/lib/api";

type Train = Record<string, unknown>;

export default function Home() {
  const [mode, setMode] = useState<"login" | "register">("register");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [from, setFrom] = useState("NDLS");
  const [to, setTo] = useState("BCT");
  const [date, setDate] = useState("02-11-2026");
  const [trains, setTrains] = useState<Train[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function authenticate() {
    setBusy(true); setMessage("");
    try {
      const result = await apiRequest(`/auth/${mode}`, {
        method: "POST", body: JSON.stringify({ email, password })
      });
      localStorage.setItem("railway_access_token", result.access_token);
      setToken(result.access_token);
      setMessage(`Signed in as ${result.user.email}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Authentication failed");
    } finally { setBusy(false); }
  }

  async function search() {
    setBusy(true); setMessage(""); setTrains([]);
    try {
      const result = await apiRequest(
        `/railway/trains/between?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&date=${encodeURIComponent(date)}`
      );
      setTrains(result.data ?? []);
      setMessage(`${(result.data ?? []).length} train(s) returned`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Train search failed");
    } finally { setBusy(false); }
  }

  async function availability(train: Train) {
    const trainNo = String(train.train_no ?? train.trainNo ?? "");
    if (!trainNo) { setMessage("Train number was not present in the provider response."); return; }
    setBusy(true);
    try {
      const result = await apiRequest(
        `/railway/availability/${trainNo}?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&date=${encodeURIComponent(date)}&travel_class=3A&quota=GN`
      );
      setMessage(JSON.stringify(result, null, 2));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Availability check failed");
    } finally { setBusy(false); }
  }

  function logout() {
    localStorage.removeItem("railway_access_token");
    setToken(null); setTrains([]); setMessage("Signed out");
  }

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-5 py-10">
      <header className="mb-10 flex items-center justify-between">
        <div><p className="text-sm font-semibold text-blue-700">RAILWAY ASSISTANT</p><h1 className="mt-1 text-3xl font-semibold">Journey search</h1><p className="mt-2 text-sm text-slate-500">Search trains and inspect segment availability.</p></div>
        {token && <button onClick={logout} className="rounded-lg border bg-white px-4 py-2 text-sm">Sign out</button>}
      </header>

      {!token ? (
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
            <Field label="Journey date (DD-MM-YYYY)" value={date} onChange={setDate} />
            <div className="flex items-end"><button disabled={busy} onClick={search} className="w-full rounded-lg bg-slate-900 p-3 text-white disabled:opacity-50">{busy ? "Searching…" : "Search trains"}</button></div>
          </div>
          <p className="mt-3 text-xs text-slate-500">Use station codes such as NDLS, JP, CUR, AII or HYB.</p>
          {trains.length > 0 && <div className="mt-8 overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b text-slate-500"><th className="p-3">Train</th><th className="p-3">Departure</th><th className="p-3">Arrival</th><th className="p-3">Duration</th><th className="p-3">Action</th></tr></thead><tbody>{trains.map((train, i) => <tr className="border-b" key={`${String(train.train_no ?? i)}-${i}`}><td className="p-3"><b>{String(train.train_no ?? "")}</b><br />{String(train.train_name ?? "")}</td><td className="p-3">{String(train.from_time ?? "—")}</td><td className="p-3">{String(train.to_time ?? "—")}</td><td className="p-3">{String(train.travel_time ?? "—")}</td><td className="p-3"><button onClick={() => availability(train)} className="rounded-md border px-3 py-2">Check 3AC</button></td></tr>)}</tbody></table></div>}
        </section>
      )}
      {message && <pre className="mt-5 overflow-x-auto whitespace-pre-wrap rounded-xl border bg-white p-4 text-sm text-slate-700">{message}</pre>}
      <p className="mt-8 text-xs text-slate-400">Availability is provider-supplied and can change. Verify on official railway channels before booking.</p>
    </main>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label className="block text-sm">{label}<input value={value} onChange={e => onChange(e.target.value)} className="mt-1 w-full rounded-lg border p-3" /></label>;
}
