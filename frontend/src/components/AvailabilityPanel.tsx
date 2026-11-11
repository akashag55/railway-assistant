import type { AvailabilityDay, AvailabilityState, AvailabilityStatus } from "@/types/railway";

export type Kind = AvailabilityStatus;

export const KIND_STYLE: Record<Kind, { label: string; badge: string; card: string }> = {
  available: { label: "Available", badge: "bg-green-100 text-green-800", card: "border-green-200" },
  rac: { label: "RAC", badge: "bg-amber-100 text-amber-800", card: "border-amber-200" },
  waitlist: { label: "Waitlist", badge: "bg-orange-100 text-orange-800", card: "border-orange-200" },
  unavailable: { label: "Not available", badge: "bg-red-100 text-red-800", card: "border-red-200" },
  unknown: { label: "Unknown", badge: "bg-slate-100 text-slate-700", card: "border-slate-200" },
};

const UNITS: Partial<Record<Kind, string>> = { waitlist: "on waitlist", available: "seats", rac: "RAC" };

function countText(day: AvailabilityDay) {
  const unit = UNITS[day.status];
  if (day.count !== null && unit) return { value: String(day.count), unit };
  return { value: day.text || "—", unit: "" };
}

function formatDate(value: string) {
  const [d, m, y] = value.split("-").map(Number);
  const date = new Date(y, (m ?? 1) - 1, d);
  if (!d || !m || !y || Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
}

const rupees = (n: number | null | undefined) => (typeof n === "number" ? `₹${n.toLocaleString("en-IN")}` : "—");

export function AvailabilityPanel({ result, searchedDate }: { result: AvailabilityState; searchedDate: string }) {
  if (result.state === "loading") {
    return <p className="text-sm text-slate-500" role="status">Checking availability…</p>;
  }
  if (result.state === "error") {
    return <p className="text-sm text-red-700" role="alert">{result.message}</p>;
  }

  const { data } = result;
  const fare = data.fare;
  const fetchedAt = new Date(data.fetched_at);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-xs text-slate-600">
        <span>
          <b>{data.from_code}</b> {data.from_name && `(${data.from_name})`} → <b>{data.to_code}</b> {data.to_name && `(${data.to_name})`}
        </span>
        <span>Class <b>{data.travel_class}</b></span>
        <span>Quota <b>{data.quota}</b></span>
        {fare?.total != null && (
          <span title={`Base ${rupees(fare.base)} · Reservation ${rupees(fare.reservation)} · Superfast ${rupees(fare.superfast)} · GST ${rupees(fare.tax)}`}>
            Fare <b className="text-slate-900">{rupees(fare.total)}</b>
          </span>
        )}
      </div>

      {data.days.length === 0 ? (
        <p className="text-sm text-slate-500">No availability was returned for this train and class.</p>
      ) : (
        <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {data.days.map((day) => {
            const style = KIND_STYLE[day.status];
            const count = countText(day);
            const selected = day.date === searchedDate;
            return (
              <li
                key={day.date}
                title={day.raw_status ? `Provider status: ${day.raw_status}` : undefined}
                className={`rounded-lg border bg-white p-3 ${style.card} ${selected ? "ring-2 ring-slate-900" : ""}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-medium text-slate-600">
                    {formatDate(day.date)}
                    {selected && <span className="ml-1 text-slate-400">(selected)</span>}
                  </span>
                  <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${style.badge}`}>
                    {day.status === "unknown" && day.text ? day.text : style.label}
                  </span>
                </div>
                <p className="mt-2 text-lg font-semibold text-slate-900">
                  {count.value} {count.unit && <span className="text-sm font-normal text-slate-500">{count.unit}</span>}
                </p>
                {day.prediction && day.status !== "available" && (
                  <p className="mt-1 text-xs text-slate-500">Prediction: {day.prediction}</p>
                )}
                {day.can_book === false && <p className="mt-1 text-xs text-red-700">Booking not open</p>}
              </li>
            );
          })}
        </ul>
      )}

      <p className="text-xs text-slate-400">
        Fetched {fetchedAt.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })} from {data.provider === "railkit" ? "RailKit" : data.provider}.
        Predictions are estimates, not confirmations. Hover a card for the raw status.
      </p>
    </div>
  );
}
