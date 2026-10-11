const DAY = 24 * 60 * 60 * 1000;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

export function toDateValue(iso) {
  if (!ISO_DATE.test(iso ?? "")) return NaN;
  const timestamp = Date.parse(`${iso}T00:00:00Z`);
  return Number.isFinite(timestamp) && new Date(timestamp).toISOString().slice(0, 10) === iso
    ? timestamp
    : NaN;
}

export function dayCount(start, end) {
  const a = toDateValue(start);
  const b = toDateValue(end);
  if (!Number.isFinite(a) || !Number.isFinite(b)) return NaN;
  return Math.round((b - a) / DAY) + 1;
}

export function addDays(iso, days) {
  const value = toDateValue(iso);
  if (!Number.isFinite(value)) return "";
  return new Date(value + days * DAY).toISOString().slice(0, 10);
}

export function overlap(first, second) {
  if (!first || !second) return null;
  const start = first.start_date > second.start_date ? first.start_date : second.start_date;
  const end = first.end_date < second.end_date ? first.end_date : second.end_date;
  return toDateValue(start) <= toDateValue(end) ? { start, end } : null;
}

export function suggestedPeriod(coverage, preferredDays = 14) {
  if (!coverage) return null;
  const proposedStart = addDays(coverage.end, -(preferredDays - 1));
  return { start: proposedStart < coverage.start ? coverage.start : proposedStart, end: coverage.end };
}

export function validatePeriod(start, end, coverage, maxDays = 31) {
  if (!coverage || !Number.isFinite(toDateValue(start)) || !Number.isFinite(toDateValue(end))) {
    return "Choose a valid start and end date.";
  }
  const days = dayCount(start, end);
  if (days < 1) return "The end date cannot be before the start date.";
  if (days > maxDays) return `Choose a range of no more than ${maxDays} days.`;
  if (start < coverage.start || end > coverage.end) {
    return `Choose dates within the shared coverage: ${coverage.start} to ${coverage.end}.`;
  }
  return "";
}

export function formatDate(iso, options = { day: "numeric", month: "short", year: "numeric" }) {
  if (!Number.isFinite(toDateValue(iso))) return iso || "—";
  return new Intl.DateTimeFormat("en-GB", { ...options, timeZone: "UTC" }).format(new Date(`${iso}T00:00:00Z`));
}
