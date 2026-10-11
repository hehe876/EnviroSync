export const METRICS = Object.freeze({
  temp_max_c: { title: "Maximum temperature", short: "Max temp", unit: "°C", precision: 1 },
  temp_min_c: { title: "Minimum temperature", short: "Min temp", unit: "°C", precision: 1 },
  precipitation_mm: { title: "Precipitation", short: "Rainfall", unit: "mm", precision: 1 },
});

export function formatValue(value, unit = "", precision = 1) {
  const numeric = value === null || value === undefined || value === "" ? NaN : Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return `${numeric.toFixed(precision)}${unit ? ` ${unit}` : ""}`;
}

export function meanValue(rows, metric) {
  const values = (rows || []).map((item) => item?.[metric]).filter((value) => typeof value === "number" && Number.isFinite(value));
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
}

export function sumValue(rows, metric) {
  const values = (rows || []).map((item) => item?.[metric]).filter((value) => typeof value === "number" && Number.isFinite(value));
  return values.length ? values.reduce((a, b) => a + b, 0) : null;
}

export function toCSV(rows, columns) {
  const escape = (value) => {
    const text = value === null || value === undefined ? "" : String(value);
    // Spreadsheet readers may execute untrusted text beginning with formula sigils.
    const safe = typeof value === "string" && /^[\s]*[=+@-]/.test(text) ? `'${text}` : text;
    return `"${safe.replace(/"/g, '""')}"`;
  };
  return [columns.map((column) => escape(column.label)).join(","),
    ...rows.map((row) => columns.map((column) => escape(row[column.key])).join(","))].join("\r\n") + "\r\n";
}

export function comparePointsToCSV(points, city1, city2) {
  return toCSV(points, [
    { key: "date", label: "Date" },
    { key: city1, label: city1 },
    { key: city2, label: city2 },
  ]);
}
