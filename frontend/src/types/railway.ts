// Shapes returned by GET /railway/availability/{train_no} (RailKit data, passed through).
// Fields are optional where RailKit may omit them; never fill in missing values.

export type AvailabilityDay = {
  date: string; // D-MM-YYYY or DD-MM-YYYY
  status?: string; // e.g. "WAITLIST"
  availabilityText?: string; // e.g. "WL 5"
  rawStatus?: string; // e.g. "RLWL16/WL5"
  prediction?: string; // RailKit's own estimate, e.g. "81% Chance"
  predictionPercentage?: number;
  canBook?: boolean;
};

export type AvailabilityFare = {
  baseFare?: number;
  reservationCharge?: number;
  superfastCharge?: number;
  serviceTax?: number;
  totalFare?: number;
};

export type AvailabilityData = {
  train?: {
    trainNo?: string;
    trainName?: string;
    from?: string;
    to?: string;
    fromStationName?: string;
    toStationName?: string;
    travelClass?: string;
    quota?: string;
  };
  fare?: AvailabilityFare;
  availability?: AvailabilityDay[];
};

export type AvailabilityState =
  | { state: "loading" }
  | { state: "error"; message: string }
  | { state: "done"; data: AvailabilityData; fetchedAt: Date };

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
    level: "available" | "rac" | "waitlist" | "unavailable" | "unknown";
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
