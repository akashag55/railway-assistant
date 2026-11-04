import type { AvailabilityDay, AvailabilityState } from "@/types/railway";

type Kind = "available" | "rac" | "waitlist" | "unavailable" | "unknown";

const KIND_STYLE: Record<Kind, { label: string; badge: string; card: string }> = {
  available: { label: "Available", badge: "bg-green-100 text-green-800", card: "border-green-200" },
  rac: { label: "RAC", badge: "bg-amber-100 text-amber-800", card: "border-amber-200" },
  waitlist: { label: "Waitlist", badge: "bg-orange-100 text-orange-800", card: "border-orange-200" },
  unavailable: { label: "Not available", badge: "bg-red-100 text-red-800", card: "border-red-200" },
  unknown: { label: "Unknown", badge: "bg-slate-100 text-slate-700", card: "border-slate-200" },
};

// Map RailKit's status text to a display category. Only exact, known meanings are
// mapped; anything else stays "unknown" and shows RailKit's own text.
function classify(day: AvailabilityDay): Kind {
  const s = `${day.status ?? ""} ${day.availabilityText ?? ""}`.toUpperCase();
  if (/REGRET|NOT AVAILABLE|CANCELLED|DEPARTED|CHART PREPARED/.test(s)) return "unavailable";
  if (/\bRAC\b/.test(s)) return "rac";
  if (/WAITLIST|\bWL\b|GNWL|RLWL|PQWL|TQWL/.test(s)) return "waitlist";
  if (/AVAILABLE|\bAVL\b|CURR_AVBL/.test(s)) return "available";
  return "unknown";
}

function countText(kind: Kind, day: AvailabilityDay) {
  const n = day.availabilityText?.match(/\d+/)?.[0];
  if (n && kind === "waitlist") return { value: String(Number(n)), unit: "on waitlist" };
  if (n && kind === "available") return { value: String(Number(n)), unit: "seats" };
  if (n && kind === "rac") return { value: String(Number(n)), unit: "RAC" };
  return { value: day.availabilityText || day.status || "—", unit: "" };
}

function formatDate(value: string) {
  const [d, m, y] = value.split("-").map(Number);
  const date = new Date(y, (m ?? 1) - 1, d);
  if (!d || !m || !y || Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
}

function sameDate(a: string, b: string) {
  const norm = (v: string) => v.split("-").map(Number).join("-");
  return norm(a) === norm(b);
}

const rupees = (n?: number) => (typeof n === "number" ? `₹${n.toLocaleString("en-IN")}` : "—");

export function AvailabilityPanel({ result, searchedDate }: { result: AvailabilityState; searchedDate: string }) {
  if (result.state === "loading") {
    return <p className="text-sm text-slate-500" role="status">Checking availability…</p>;
  }
  if (result.state === "error") {
    return <p className="text-sm text-red-700" role="alert">{result.message}</p>;
  }

  const { data, fetchedAt } = result;
  const days = data.availability ?? [];
  const t = data.train;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-xs text-slate-600">
        {t && (
          <span>
            <b>{t.from}</b> {t.fromStationName && `(${t.fromStationName})`} → <b>{t.to}</b> {t.toStationName && `(${t.toStationName})`}
          </span>
        )}
        {t?.travelClass && <span>Class <b>{t.travelClass}</b></span>}
        {t?.quota && <span>Quota <b>{t.quota}</b></span>}
        {data.fare?.totalFare !== undefined && (
          <span
            title={`Base ${rupees(data.fare.baseFare)} · Reservation ${rupees(data.fare.reservationCharge)} · Superfast ${rupees(data.fare.superfastCharge)} · GST ${rupees(data.fare.serviceTax)}`}
          >
            Fare <b className="text-slate-900">{rupees(data.fare.totalFare)}</b>
          </span>
        )}
      </div>

      {days.length === 0 ? (
        <p className="text-sm text-slate-500">RailKit returned no availability for this train and class.</p>
      ) : (
        <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {days.map((day) => {
            const kind = classify(day);
            const style = KIND_STYLE[kind];
            const count = countText(kind, day);
            const selected = sameDate(day.date, searchedDate);
            return (
              <li
                key={day.date}
                title={day.rawStatus ? `RailKit status: ${day.rawStatus}` : undefined}
                className={`rounded-lg border bg-white p-3 ${style.card} ${selected ? "ring-2 ring-slate-900" : ""}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-medium text-slate-600">
                    {formatDate(day.date)}
                    {selected && <span className="ml-1 text-slate-400">(selected)</span>}
                  </span>
                  <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${style.badge}`}>
                    {kind === "unknown" && day.status ? day.status : style.label}
                  </span>
                </div>
                <p className="mt-2 text-lg font-semibold text-slate-900">
                  {count.value} {count.unit && <span className="text-sm font-normal text-slate-500">{count.unit}</span>}
                </p>
                {day.prediction && (
                  <p className="mt-1 text-xs text-slate-500">RailKit prediction: {day.prediction}</p>
                )}
                {day.canBook === false && <p className="mt-1 text-xs text-red-700">Booking not open</p>}
              </li>
            );
          })}
        </ul>
      )}

      <p className="text-xs text-slate-400">
        Fetched {fetchedAt.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })} from RailKit. Predictions are
        RailKit estimates, not confirmations. Hover a card for the raw status.
      </p>
    </div>
  );
}
