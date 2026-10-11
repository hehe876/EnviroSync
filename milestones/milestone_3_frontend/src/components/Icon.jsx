import React from "react";

const paths = {
  layers: "M4 7.5 12 3l8 4.5-8 4.5L4 7.5Zm0 5 8 4.5 8-4.5M4 17l8 4 8-4",
  globe: "M12 2a10 10 0 1 0 0 20 10 10 0 1 0 0-20Zm-10 10h20M12 2c-3 3-3 17 0 20M12 2c3 3 3 17 0 20",
  activity: "M3 12h4l3-7 4 14 3-7h4",
  shield: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Zm-4-10 3 3 5-6",
  download: "M12 3v12m-4-4 4 4 4-4M5 17v3h14v-3",
  refresh: "M20 7v5h-5M4 17v-5h5m-3-3a7 7 0 0 1 12-2l2 5M4 12l2 5a7 7 0 0 0 12-2",
  calendar: "M5 4h14a2 2 0 0 1 2 2v14H3V6a2 2 0 0 1 2-2ZM3 10h18M8 2v4m8-4v4",
  cloud: "M7 18H6a4 4 0 0 1-1-7.87A7 7 0 0 1 18.6 9a4.5 4.5 0 0 1-.6 9H7Z",
  server: "M3 4h18v7H3V4Zm0 9h18v7H3v-7ZM7 8h.01M7 17h.01M11 8h7M11 17h7",
  arrowRight: "M4 12h16m-6-6 6 6-6 6",
  chevron: "m9 18 6-6-6-6",
  thermometer: "M9 14V5a3 3 0 0 1 6 0v9a5 5 0 1 1-6 0ZM12 7v11",
  droplet: "M12 2C8 8 5 11 5 15a7 7 0 0 0 14 0c0-4-3-7-7-13Z",
  chart: "M4 20V5m0 15h17M7 15l4-5 4 3 5-7",
  alert: "M12 3 2 21h20L12 3Zm0 6v5m0 3v.01",
  check: "M4 12 9 17 20 6",
  info: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20Zm0-11v6m0-10v.01",
  close: "M5 5l14 14M19 5 5 19",
  bars: "M4 6h16M4 12h16M4 18h16",
  location: "M12 22s7-7 7-12a7 7 0 1 0-14 0c0 5 7 12 7 12Zm0-9a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
  database: "M21 5c0 2-4 3-9 3S3 7 3 5s4-3 9-3 9 1 9 3ZM3 5v14c0 2 4 3 9 3s9-1 9-3V5M3 12c0 2 4 3 9 3s9-1 9-3",
  external: "M12 5h7v7M19 5l-9 9M19 14v5H5V5h5",
};

export default function Icon({ name, size = 20, className = "", title }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden={title ? undefined : true}
      role={title ? "img" : undefined} className={className}>
      {title && <title>{title}</title>}
      <path d={paths[name] || paths.info} />
    </svg>
  );
}
