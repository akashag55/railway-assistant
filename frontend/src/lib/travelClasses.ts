// Reserved classes RailKit's seat-availability endpoint accepts (see
// https://railkit.in/docs/seat-availability), in a sensible display order.
// Keep in sync with the travel_class pattern in backend/app/api/v1/railway.py.
export const BOOKABLE_CLASSES = [
  "1A", "EA", "EC", "2A", "FC", "3A", "3E", "CC", "SL", "2S",
  "VS", "VC", "VA", "CH", "HS",
] as const;

// Names only for well-known codes; others are shown as the bare code.
const CLASS_NAMES: Record<string, string> = {
  "1A": "First AC",
  "2A": "AC 2 Tier",
  "3A": "AC 3 Tier",
  "3E": "AC 3 Economy",
  SL: "Sleeper",
  CC: "AC Chair Car",
  EC: "Executive Chair Car",
  EA: "Anubhuti Class",
  FC: "First Class",
  "2S": "Second Sitting",
};

export function className(code: string) {
  return CLASS_NAMES[code] ?? code;
}

/**
 * Bookable classes listed for a train in search results (`classes_of_travel`,
 * e.g. "2A,3A,SL,GEN,PWD"). Non-bookable codes (GEN, PWD, PC, LDS…) are dropped.
 * Returns [] when RailKit did not list any classes.
 */
export function trainClasses(classesOfTravel: unknown): string[] {
  if (typeof classesOfTravel !== "string") return [];
  const listed = new Set(classesOfTravel.split(",").map((c) => c.trim().toUpperCase()));
  return BOOKABLE_CLASSES.filter((c) => listed.has(c));
}
