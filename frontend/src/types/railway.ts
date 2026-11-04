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
