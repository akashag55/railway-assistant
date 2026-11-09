"use client";

import { useCallback, useEffect, useState } from "react";
import { apiRequest, isAuthError } from "@/lib/api";
import { BOOKABLE_CLASSES, className } from "@/lib/travelClasses";
import { KIND_STYLE } from "@/components/AvailabilityPanel";
import type { RouteLeg, RouteOption, RouteSearch } from "@/types/railway";

const POLL_MS = 3000;

const isActive = (s: RouteSearch | null) => s?.status === "queued" || s?.status === "running";

function duration(minutes: number) {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h ? `${h}h ${m}m` : `${m}m`;
}

function when(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const day = d.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
  return `${day}, ${iso.slice(11, 16)}`;
}

const rupees = (n: number) => `₹${n.toLocaleString("en-IN")}`;

function LegRow({ leg }: { leg: RouteLeg }) {
  const a = leg.availability;
  const style = KIND_STYLE[a.level];
  const longer = leg.ticket_from !== leg.board || leg.ticket_to !== leg.alight;
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border bg-white p-3 text-sm">
      <div>
        <p><b>{leg.train_no}</b> {leg.train_name}</p>
        <p className="text-slate-600" title={`${leg.board_name} → ${leg.alight_name}`}>
          <b>{leg.board}</b> {when(leg.depart)} → <b>{leg.alight}</b> {when(leg.arrive)} · {duration(leg.minutes)}
        </p>
        {longer && <p className="text-xs text-slate-500">Ticket: {leg.ticket_from} → {leg.ticket_to}</p>}
      </div>
      <div title={a.raw ? `RailKit status: ${a.raw}` : undefined}>
        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${style.badge}`}>{style.label}</span>
        <p className="mt-1 font-semibold">{a.text ?? "—"} <span className="text-xs font-normal text-slate-500">{a.travel_class}</span></p>
        {a.prediction && a.level !== "available" && <p className="text-xs text-slate-500">RailKit prediction: {a.prediction}</p>}
        {a.fare !== null && <p className="text-xs text-slate-500">{rupees(a.fare)}</p>}
        {a.error && <p className="max-w-xs text-xs text-red-700">{a.error}</p>}
      </div>
    </div>
  );
}

function OptionCard({ option }: { option: RouteOption }) {
  const style = KIND_STYLE[option.overall];
  return (
    <li className={`rounded-xl border bg-slate-50 p-3 ${style.card}`}>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold">{option.title}</p>
        <p className="text-xs text-slate-600">
          <span className={`mr-2 rounded-full px-2 py-0.5 font-semibold ${style.badge}`}>{style.label}</span>
          {duration(option.total_minutes)}{option.total_fare !== null && ` · ${rupees(option.total_fare)}`}
        </p>
      </div>
      <div className="space-y-2">
        {option.legs.map((leg, i) => (
          <div key={`${leg.train_no}-${leg.ticket_from}-${leg.ticket_to}`} className="space-y-2">
            <LegRow leg={leg} />
            {option.transfers[i] && (
              <p className="px-1 text-xs text-slate-600">
                {option.transfers[i].same_train
                  ? `Stay on the train at ${option.transfers[i].at}; the second ticket starts here.`
                  : `Change at ${option.transfers[i].at}${option.transfers[i].to !== option.transfers[i].at ? ` → ${option.transfers[i].to}` : ""}, wait ${duration(option.transfers[i].wait_minutes)}`}
              </p>
            )}
          </div>
        ))}
      </div>
      {option.warnings.map(w => <p key={w} className="mt-2 text-xs text-amber-800">{w}</p>)}
    </li>
  );
}

function Group({ title, options, searching }: { title: string; options: RouteOption[]; searching: boolean }) {
  return (
    <div>
      <h4 className="mb-2 text-sm font-semibold text-slate-700">{title} ({options.length})</h4>
      {options.length === 0
        ? <p className="text-sm text-slate-500">{searching ? "Nothing yet…" : "No routes found."}</p>
        : <ul className="space-y-3">{options.map((o, i) => <OptionCard key={i} option={o} />)}</ul>}
    </div>
  );
}

export function RouteFinder({ from, to, journeyDate, onSessionExpired }: {
  from: string;
  to: string;
  journeyDate: string; // DD-MM-YYYY of the current results; "" until a search has run
  onSessionExpired: (error: unknown) => void;
}) {
  const [travelClass, setTravelClass] = useState("3A");
  const [search, setSearch] = useState<RouteSearch | null>(null);
  const [error, setError] = useState("");

  const fail = useCallback((e: unknown) => {
    if (isAuthError(e)) onSessionExpired(e);
    else setError(e instanceof Error ? e.message : "Route search request failed");
  }, [onSessionExpired]);

  // Pick up the latest search, so progress survives a page refresh or re-login.
  useEffect(() => {
    apiRequest("/routes/search?limit=1").then((list: RouteSearch[]) => setSearch(list[0] ?? null)).catch(fail);
  }, [fail]);

  const active = isActive(search);
  const searchId = search?.id;
  useEffect(() => {
    if (!active || !searchId) return;
    const timer = setInterval(() => {
      apiRequest(`/routes/search/${searchId}`).then(setSearch).catch(fail);
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [active, searchId, fail]);

  async function start() {
    setError("");
    try {
      setSearch(await apiRequest("/routes/search", {
        method: "POST",
        body: JSON.stringify({ from, to, date: journeyDate, travel_class: travelClass }),
      }));
    } catch (e) { fail(e); }
  }

  async function cancel() {
    if (!search) return;
    try { await apiRequest(`/routes/search/${search.id}/cancel`, { method: "POST" }); } catch (e) { fail(e); }
  }

  const groups = search?.results.groups;
  const p = search?.progress;

  return (
    <div className="mt-8 border-t pt-6">
      <h3 className="text-lg font-semibold">Find best route</h3>
      <p className="mt-1 text-sm text-slate-500">
        Waitlisted? This searches split tickets, longer tickets and connecting trains in the background. It can take a
        while and uses many RailKit requests.
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <select aria-label="Class for best route search" value={travelClass} onChange={e => setTravelClass(e.target.value)} className="rounded-md border bg-white px-2 py-2 text-sm">
          {BOOKABLE_CLASSES.map(c => <option key={c} value={c}>{c}{className(c) !== c ? ` · ${className(c)}` : ""}</option>)}
        </select>
        {active
          ? <button onClick={cancel} className="rounded-lg border bg-white px-4 py-2 text-sm">Cancel search</button>
          : <button onClick={start} disabled={!journeyDate} className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">Find best route{journeyDate ? ` for ${journeyDate}` : ""}</button>}
        {!journeyDate && !active && <span className="text-xs text-slate-500">Search trains first.</span>}
      </div>
      {error && <p className="mt-3 text-sm text-red-700" role="alert">{error}</p>}

      {search && (
        <div className="mt-5 space-y-4">
          <div className="rounded-lg border bg-slate-50 p-3 text-sm" role="status">
            <p className="font-medium">{search.from_code} → {search.to_code} · {search.journey_date} · {search.travel_class} · <span className="capitalize">{search.status}</span></p>
            <p className="text-slate-600">{p?.phase}</p>
            <p className="text-xs text-slate-500">{p?.requests ?? 0} RailKit requests · {p?.checks ?? 0} availability checks · {p?.options ?? 0} routes considered</p>
            {p?.stop_reason && <p className="mt-1 text-xs text-amber-800">{p.stop_reason}</p>}
            {search.error && <p className="mt-1 text-red-700">{search.error}</p>}
            {search.results.notes?.map(n => <p key={n} className="mt-1 text-xs text-amber-800">{n}</p>)}
          </div>
          {groups && (
            <div className="grid gap-5 lg:grid-cols-2">
              <Group title="No train change" options={groups.no_change} searching={active} />
              <Group title="With train change" options={groups.with_change} searching={active} />
            </div>
          )}
          <p className="text-xs text-slate-400">Availability changes quickly; these are the statuses at the time each was checked. Predictions are RailKit estimates, not confirmations. Split and longer tickets are separate bookings: verify on official railway channels before booking.</p>
        </div>
      )}
    </div>
  );
}
