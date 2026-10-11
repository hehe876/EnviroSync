import test from "node:test";
import assert from "node:assert/strict";
import { formatValue, meanValue, sumValue, toCSV, comparePointsToCSV } from "./format.mjs";

test("missing data stays missing, never a fabricated zero", () => {
  assert.equal(formatValue(null, "°C"), "—");
  assert.equal(meanValue([{ temp_max_c: null }], "temp_max_c"), null);
  assert.equal(sumValue([{ precipitation_mm: null }], "precipitation_mm"), null);
  assert.equal(meanValue([{temp_max_c: 10}, {temp_max_c: 20}], "temp_max_c"), 15);
  assert.equal(sumValue([{precipitation_mm: 2}, {precipitation_mm: 3}], "precipitation_mm"), 5);
});

test("comparison CSV includes only returned data and correctly escapes values", () => {
  const csv = comparePointsToCSV([{ date: "2025-07-01", chennai: 31, london: null }], "chennai", "london");
  assert.match(csv, /"date","chennai","london"/i);
  assert.match(csv, /"2025-07-01","31",""/);
  assert.equal(csv.split("\r\n").length, 3);
  assert.equal(toCSV([{ name: 'A, "B"' }], [{ key: "name", label: "Name" }]), '"Name"\r\n"A, ""B"""\r\n');
  assert.equal(toCSV([{ name: '=HYPERLINK("http://evil")' }], [{ key: "name", label: "Name" }]), '"Name"\r\n"\'=HYPERLINK(""http://evil"")"\r\n');
});
