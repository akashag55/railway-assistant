// App-owned shapes returned by the backend (see backend/app/schemas/railway.py).
// Optional values are null when the provider did not supply them; never fill them in.

export type AvailabilityStatus = "available" | "rac" | "waitlist" | "unavailable" | "unknown";

// GET /railway/trains/between
export type TrainSummary = {
  train_no: string;
  train_name: string;
  from_code: string;
  from_name: string | null;
  to_code: string;
  to_name: string | null;
  departure: string | null; // HH:MM
  arrival: string | null;
  duration_minutes: number | null;
  running_days: string[]; // e.g. ["Mon", "Wed"]
  classes: string[]; // bookable classes; empty when the provider listed none
  distance_km: number | null;
};

export type TrainSearchResult = {
  provider: string;
  fetched_at: string;
  from_code: string;
  to_code: string;
  date: string | null;
  trains: TrainSummary[];
};

// GET /railway/availability/{train_no}
export type AvailabilityDay = {
  date: string; // DD-MM-YYYY
  status: AvailabilityStatus;
  count: number | null;
  text: string | null; // provider text, e.g. "WL 5"
  raw_status: string | null;
  prediction: string | null; // provider estimate, not a confirmation
  prediction_pct: number | null;
  can_book: boolean | null;
};

export type Fare = {
  base: number | null;
  reservation: number | null;
  superfast: number | null;
  tax: number | null;
  total: number | null;
};

export type AvailabilityResult = {
  provider: string;
  fetched_at: string;
  train_no: string;
  train_name: string | null;
  from_code: string;
  from_name: string | null;
  to_code: string;
  to_name: string | null;
  travel_class: string;
  quota: string;
  fare: Fare | null;
  days: AvailabilityDay[];
};

export type AvailabilityState =
  | { state: "loading" }
  | { state: "error"; message: string }
  | { state: "done"; data: AvailabilityResult };

// Best-route search (GET /routes/search/{id}).
export type RouteLeg = {
  train_no: string;
  train_name: string;
  board: string;
  board_name: string;
  alight: string;
  alight_name: string;
  ticket_from: string;
  ticket_to: string;
  journey_date: string;
  depart: string; // ISO local time
  arrive: string;
  minutes: number;
  availability: {
    travel_class: string;
    level: AvailabilityStatus;
    count: number | null;
    text: string | null;
    raw: string | null;
    prediction: string | null;
    fare: number | null;
    error: string | null;
  };
};

export type RouteOption = {
  kind: "direct" | "split" | "longer" | "connection";
  title: string;
  group: "no_change" | "with_change";
  overall: RouteLeg["availability"]["level"];
  total_minutes: number;
  total_fare: number | null;
  legs: RouteLeg[];
  transfers: { at: string; to: string; wait_minutes: number; same_train: boolean }[];
  warnings: string[];
};

export type RouteSearch = {
  id: number;
  status: "queued" | "running" | "completed" | "cancelled" | "failed";
  from_code: string;
  to_code: string;
  journey_date: string;
  travel_class: string;
  progress: { phase?: string; requests?: number; checks?: number; options?: number; stop_reason?: string | null };
  results: { groups?: { no_change: RouteOption[]; with_change: RouteOption[] }; notes?: string[] };
  error: string | null;
};
