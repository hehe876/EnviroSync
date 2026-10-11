import test from "node:test";
import assert from "node:assert/strict";
import { addDays, dayCount, overlap, suggestedPeriod, toDateValue, validatePeriod } from "./dates.mjs";

test("canonical calendar date parser rejects invalid calendar days", () => {
  assert.equal(Number.isFinite(toDateValue("2025-02-29")), false);
  assert.equal(Number.isFinite(toDateValue("2024-02-29")), true);
  assert.equal(Number.isFinite(toDateValue("2025-7-01")), false);
});

test("inclusive windows allow 31 days but reject 32", () => {
  const coverage = { start: "2025-01-01", end: "2025-12-31" };
  assert.equal(dayCount("2025-07-01", "2025-07-31"), 31);
  assert.equal(validatePeriod("2025-07-01", "2025-07-31", coverage), "");
  assert.match(validatePeriod("2025-07-01", "2025-08-01", coverage), /31/);
});

test("rejects inverted windows and dates not present in published coverage", () => {
  const coverage = { start: "2025-01-01", end: "2025-12-31" };
  assert.match(validatePeriod("2025-12-31", "2025-01-01", coverage), /before/);
  assert.match(validatePeriod("2024-12-31", "2025-01-01", coverage), /coverage/);
});

test("overlapping city coverage is intersected rather than guessing a new date", () => {
  assert.deepEqual(overlap(
    { start_date: "2024-01-01", end_date: "2025-09-30" },
    { start_date: "2025-02-01", end_date: "2025-12-31" }),
  { start: "2025-02-01", end: "2025-09-30" });
  assert.equal(overlap(
    { start_date: "2024-01-01", end_date: "2024-12-31" },
    { start_date: "2025-01-01", end_date: "2025-12-31" }), null);
});

test("default range uses latest 14 available days, not current device date", () => {
  assert.deepEqual(suggestedPeriod({ start: "2025-12-01", end: "2025-12-31" }),
    { start: "2025-12-18", end: "2025-12-31" });
  assert.deepEqual(suggestedPeriod({ start: "2025-12-29", end: "2025-12-31" }),
    { start: "2025-12-29", end: "2025-12-31" });
  assert.equal(addDays("2024-02-28", 1), "2024-02-29");
});
