import React, { useMemo, useState } from "react";
import { formatDate } from "../lib/dates.mjs";
import { formatValue } from "../lib/format.mjs";

const W = 940;
const H = 306;
const LEFT = 58;
const RIGHT = 23;
const TOP = 24;
const BOTTOM = 54;
const COLORS = ["#0e8b83", "#ee9957"];

function segments(points, city, x, y) {
  const segments = [];
  let current = [];
  points.forEach((point, index) => {
    const val = point?.[city];
    if (typeof val === "number" && Number.isFinite(val)) current.push(`${current.length ? "L" : "M"}${x(index).toFixed(1)},${y(val).toFixed(1)}`);
    else if (current.length) { segments.push(current.join(" ")); current = []; }
  });
  if (current.length) segments.push(current.join(" "));
  return segments;
}

export default function SeriesChart({ data, firstName, secondName }) {
  const [hovered, setHovered] = useState(null);
  const chart = useMemo(() => {
    const points = data?.points || [];
    const values = points.flatMap((row) => [row[firstName], row[secondName]])
      .filter((value) => typeof value === "number" && Number.isFinite(value));
    if (!points.length || !values.length) return null;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = Math.max((max - min) * 0.14, data.unit === "mm" ? 1 : 1.5);
    const low = min - padding;
    const high = max + padding;
    const innerW = W - LEFT - RIGHT;
    const innerH = H - TOP - BOTTOM;
    const x = (index) => LEFT + (points.length === 1 ? innerW / 2 : (index / (points.length - 1)) * innerW);
    const y = (value) => TOP + ((high - value) / (high - low)) * innerH;
    return { points, low, high, x, y, paths: [segments(points, firstName, x, y), segments(points, secondName, x, y)] };
  }, [data, firstName, secondName]);

  if (!chart) {
    return <div className="chart-empty">No numeric measurements were returned for this period.</div>;
  }
  const selected = hovered !== null && hovered < chart.points.length ? chart.points[hovered] : null;
  const labels = [firstName, secondName];
  const xLabels = [...new Set([0, Math.floor((chart.points.length - 1) / 4), Math.floor((chart.points.length - 1) / 2), Math.floor((chart.points.length - 1) * 3 / 4), chart.points.length - 1])];
  return (
    <div className="series-chart">
      <div className="chart-frame">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${data.metric.replaceAll("_", " ")} comparison between ${firstName} and ${secondName}. Precise values are available in the readings table.`}>
          {Array.from({ length: 5 }, (_, i) => {
            const value = chart.low + ((chart.high - chart.low) * (4 - i) / 4);
            const py = chart.y(value);
            return <g key={`y-${i}`}>
              <line x1={LEFT} x2={W - RIGHT} y1={py} y2={py} stroke="#e5eeec" strokeDasharray={i === 4 ? "0" : "4 6"} />
              <text x={LEFT - 13} y={py + 4} textAnchor="end" className="axis-label">{Number(value.toFixed(1))}</text>
            </g>;
          })}
          {xLabels.map((index) => <text key={index} x={chart.x(index)} y={H - 18} textAnchor="middle" className="axis-label">{formatDate(chart.points[index].date, { month: "short", day: "numeric" })}</text>)}
          {chart.paths.map((paths, lineIndex) => paths.map((path, sectionIndex) =>
            <path key={`${lineIndex}-${sectionIndex}`} d={path} stroke={COLORS[lineIndex]} strokeWidth="3.2" strokeLinejoin="round" strokeLinecap="round" fill="none" />
          ))}
          {selected && <line x1={chart.x(hovered)} x2={chart.x(hovered)} y1={TOP} y2={H - BOTTOM} stroke="#8caaa4" strokeDasharray="5 5" />}
          {selected && labels.map((city, index) => typeof selected[city] === "number" &&
            <circle key={city} cx={chart.x(hovered)} cy={chart.y(selected[city])} r="6.5" stroke="white" strokeWidth="3" fill={COLORS[index]} />
          )}
          <rect x={LEFT} y={TOP} width={W - LEFT - RIGHT} height={H - TOP - BOTTOM} fill="transparent"
            onPointerMove={(event) => {
              const rect = event.currentTarget.getBoundingClientRect();
              const relative = (event.clientX - rect.left) / rect.width;
              setHovered(Math.max(0, Math.min(chart.points.length - 1, Math.round(relative * (chart.points.length - 1)))));
            }} onPointerLeave={() => setHovered(null)} />
        </svg>
      </div>
      <div className="chart-footer">
        <div className="chart-legend">
          {labels.map((city, index) => <span key={city} className="legend-item"><span className="legend-line" style={{ backgroundColor: COLORS[index] }} />{city.charAt(0).toUpperCase() + city.slice(1)}</span>)}
        </div>
        <div className="chart-hover" aria-live="polite">
          {selected ? <><strong>{formatDate(selected.date)}</strong><span>{formatValue(selected[firstName], data.unit)}</span><span>{formatValue(selected[secondName], data.unit)}</span></> : <span>Move over chart to inspect a day</span>}
        </div>
      </div>
    </div>
  );
}
