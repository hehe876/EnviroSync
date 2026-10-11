import React, { useEffect, useMemo, useState } from "react";
import Icon from "./components/Icon.jsx";
import SeriesChart from "./components/SeriesChart.jsx";
import StatusPanel from "./components/StatusPanel.jsx";
import AdminUpload from "./components/AdminUpload.jsx";
import { completeAdminSignIn } from "./lib/admin.mjs";
import { createApi } from "./lib/api.mjs";
import { formatDate, overlap, suggestedPeriod, validatePeriod, dayCount } from "./lib/dates.mjs";
import { METRICS, formatValue, meanValue, sumValue, comparePointsToCSV } from "./lib/format.mjs";

const api = createApi(import.meta.env.VITE_API_BASE_URL || "");
const cityLabel = (name) => name ? name[0].toUpperCase() + name.slice(1) : "—";
const EMPTY_FILTER = { first: "", second: "", start: "", end: "", metric: "temp_max_c" };

function lookupCoverage(datasets, filters) {
  const first = datasets.find((item) => item.city === filters.first);
  const second = datasets.find((item) => item.city === filters.second);
  if (!first) return null;
  return second ? overlap(first, second) : { start: first.start_date, end: first.end_date };
}

function exportCSV(compare, filters) {
  if (!compare?.points?.length) return;
  const csv = comparePointsToCSV(compare.points, compare.city1, compare.city2);
  const blob = new Blob(["\ufeff", csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `envirosync-${filters.first}-${filters.second}-${filters.metric}-${filters.start}-${filters.end}.csv`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function SummaryTile({ icon, label, value, footer, accent }) {
  return <article className={`summary-tile ${accent || ""}`}>
    <div className="tile-top"><span>{label}</span><div className="tile-icon"><Icon name={icon} size={20} /></div></div>
    <div className="tile-number">{value}</div>
    <p>{footer}</p>
  </article>;
}

export default function App() {
  const [reload, setReload] = useState(0);
  const [health, setHealth] = useState({ loading: true, data: null, error: null });
  const [catalog, setCatalog] = useState({ loading: true, datasets: [], error: null });
  const [filters, setFilters] = useState(EMPTY_FILTER);
  const [applied, setApplied] = useState(null);
  const [comparison, setComparison] = useState({ loading: false, data: null, error: null });
  const [observations, setObservations] = useState({ loading: false, data: null, error: null });
  const [mobileNav, setMobileNav] = useState(false);
  const [adminToken, setAdminToken] = useState(null);
  const [adminExpiry, setAdminExpiry] = useState(0);
  const [adminAuthError, setAdminAuthError] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (!params.has("code") && !params.has("error")) return;
    let active = true;
    completeAdminSignIn().then(async (session) => {
      if (!session) return;
      await api.adminSession(session.accessToken);
      if (active) { setAdminToken(session.accessToken); setAdminExpiry(session.expiresAt); }
    }).catch(error => { if (active) setAdminAuthError(error.message); }).finally(() => {
      window.history.replaceState({}, "", window.location.pathname + window.location.hash);
    });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setHealth({ loading: true, data: null, error: null });
    setCatalog({ loading: true, datasets: [], error: null });
    setApplied(null);
    setComparison({ loading: false, data: null, error: null });
    setObservations({ loading: false, data: null, error: null });
    api.health({ signal: controller.signal })
      .then((data) => setHealth({ loading: false, data, error: null }))
      .catch((error) => { if (error.name !== "AbortError") setHealth({ loading: false, data: null, error }); });
    api.datasets({ signal: controller.signal })
      .then((data) => {
        if (!Array.isArray(data.datasets)) throw new Error("Invalid catalog response: datasets must be an array.");
        setCatalog({ loading: false, datasets: data.datasets, error: null });
        const first = data.datasets[0]?.city || "";
        const second = data.datasets.find((item) => item.city !== first)?.city || "";
        const base = { ...EMPTY_FILTER, first, second };
        const coverage = lookupCoverage(data.datasets, base);
        const period = suggestedPeriod(coverage);
        const next = { ...base, ...(period || { start: "", end: "" }) };
        setFilters(next);
        setApplied(period ? next : null);
      })
      .catch((error) => { if (error.name !== "AbortError") { setCatalog({ loading: false, datasets: [], error }); setApplied(null); } });
    return () => controller.abort();
  }, [reload]);

  useEffect(() => {
    if (!applied) return;
    const controller = new AbortController();
    setObservations({ loading: true, data: null, error: null });
    const query = { city: applied.first, start: applied.start, end: applied.end };
    api.observations(query, { signal: controller.signal })
      .then((data) => setObservations({ loading: false, data, error: null }))
      .catch((error) => { if (error.name !== "AbortError") setObservations({ loading: false, data: null, error }); });
    if (applied.second) {
      setComparison({ loading: true, data: null, error: null });
      api.compare({ city1: applied.first, city2: applied.second, start: applied.start, end: applied.end, metric: applied.metric }, { signal: controller.signal })
        .then((data) => setComparison({ loading: false, data, error: null }))
        .catch((error) => { if (error.name !== "AbortError") setComparison({ loading: false, data: null, error }); });
    } else {
      setComparison({ loading: false, data: null, error: null });
    }
    return () => controller.abort();
  }, [applied]);

  const coverage = useMemo(() => lookupCoverage(catalog.datasets, filters), [catalog.datasets, filters.first, filters.second]);
  const validation = validatePeriod(filters.start, filters.end, coverage);
  const dirty = JSON.stringify(filters) !== JSON.stringify(applied);
  const ready = !catalog.loading && !catalog.error && !validation && !!filters.first;
  const observationRows = observations.data?.rows || [];
  const compareData = comparison.data;
  const checked = compareData && observations.data && observations.data.sha256_verified === true &&
    Object.values(compareData.sources || {}).length === 2 && Object.values(compareData.sources).every((item) => item.sha256_verified === true);
  const busy = observations.loading || comparison.loading;

  function changeCity(key, value) {
    const next = { ...filters, [key]: value };
    const range = lookupCoverage(catalog.datasets, next);
    const period = suggestedPeriod(range);
    setFilters({ ...next, ...(period || { start: "", end: "" }) });
  }

  function applyFilters(event) {
    event.preventDefault();
    if (ready) setApplied({ ...filters });
  }

  return <div className="app-shell">
    <aside className={`sidebar ${mobileNav ? "nav-open" : ""}`}>
      <div className="brand"><div className="brand-mark"><Icon name="layers" size={23} /></div><div><strong>enviro<span>sync</span></strong><small>ENVIRONMENTAL INTELLIGENCE</small></div></div>
      <div className="nav-group"><span className="nav-label">WORKSPACE</span>
        <a href="#overview" className="nav-link active" onClick={() => setMobileNav(false)}><Icon name="chart" size={18}/>Overview</a>
        <a href="#datasets" className="nav-link" onClick={() => setMobileNav(false)}><Icon name="database" size={18}/>Datasets</a>
        <a href="#comparison" className="nav-link" onClick={() => setMobileNav(false)}><Icon name="activity" size={18}/>Compare regions</a>
        <a href="#observations" className="nav-link" onClick={() => setMobileNav(false)}><Icon name="calendar" size={18}/>Observations</a>
      </div>
      <div className="sidebar-bottom">
        <div className="side-feature"><span className="side-feature-icon"><Icon name="globe" size={18}/></span><strong>Federated by design</strong><p>One interface. Multiple AWS regions. Verified at retrieval.</p></div>
        <div className="side-foot"><span className="status-led" /> <span>Milestones 1B + 2</span><span>v0.3</span></div>
      </div>
    </aside>
    {mobileNav && <button className="nav-backdrop" aria-label="Close navigation" onClick={() => setMobileNav(false)} />}
    <main className="main-content" id="overview">
      <header className="topbar">
        <button className="mobile-menu" type="button" onClick={() => setMobileNav(!mobileNav)} aria-label="Open navigation"><Icon name="bars"/></button>
        <div className="breadcrumbs">Workspace <Icon name="chevron" size={13}/> <strong>Overview</strong></div>
        <div className="topbar-right">
          <span className={`connection-indicator ${health.data?.status === "ok" ? "online" : "offline"}`}><span />{health.loading ? "Checking API…" : health.data?.status === "ok" ? "API connected" : "API offline"}</span>
          <button type="button" className="icon-button" aria-label="Refresh datasets from API" title="Refresh catalog and data" onClick={() => setReload((previous) => previous + 1)}><Icon name="refresh" size={18}/></button>
          <div className="avatar">ES</div>
        </div>
      </header>
      <div className="page-body">
        <section className="intro-area">
          <div><div className="eyebrow"><span className="eyebrow-dot"/> YOUR DATA, WITHOUT BORDERS</div><h1>Environmental overview<span className="title-period">.</span></h1><p>Explore historical environmental measurements across regions, backed by verifiable S3 data.</p></div>
          <div className="intro-icon"><Icon name="globe" size={35}/></div>
        </section>
        <div className="disclaimer"><Icon name="info" size={16}/><span>Historical observations (ERA5 for preloaded cities; administrator-provided for uploads) — not live weather or forecasts.</span></div>
        {catalog.error && <StatusPanel title="Global catalog unavailable" description={catalog.error.message} code={catalog.error.code} retry={() => setReload((v) => v + 1)} />}
        {!catalog.error && !catalog.loading && !catalog.datasets.length && <StatusPanel title="No published datasets" description="Hosting is connected, but no datasets have been published yet. Data integration comes next." type="notice" retry={() => setReload((v) => v + 1)}/>}
        <div className="section-heading" id="datasets"><div><span className="section-kicker">01 / SOURCES</span><h2>Federated datasets</h2></div><span className="section-subtext">{catalog.loading ? "Loading catalog…" : `${catalog.datasets.length} registered ${catalog.datasets.length === 1 ? "dataset" : "datasets"}`}</span></div>
        <AdminUpload accessToken={adminToken} expiresAt={adminExpiry} authError={adminAuthError} onUploaded={() => setReload(v => v + 1)} onSignOut={() => { setAdminToken(null); setAdminExpiry(0); }} />
        <div className="dataset-row">
          {catalog.loading ? <><div className="skeleton dataset-skeleton"/><div className="skeleton dataset-skeleton"/></> : catalog.datasets.map((item, index) => <article className="dataset-card" key={item.dataset_id}>
            <div className="dataset-top"><span className={`city-icon ${index % 2 ? "london" : "chennai"}`}><Icon name="location" size={22}/></span><span className="region-chip">{item.aws_region}</span></div>
            <h3>{item.display_name || cityLabel(item.city)} <span className="country">{item.country}</span></h3>
            <div className="dataset-meta"><Icon name="database" size={15}/>{item.observation_count?.toLocaleString() || "—"} daily observations</div>
            <div className="dataset-border"/>
            <div className="dataset-detail"><span>Available period</span><strong>{formatDate(item.start_date, { month: "short", year: "numeric" })} – {formatDate(item.end_date, { month: "short", year: "numeric" })}</strong></div>
          </article>)}
        </div>
        <section className="filters-section" aria-labelledby="filters-heading">
          <div className="section-heading compact"><div><span className="section-kicker">02 / EXPLORE</span><h2 id="filters-heading">Explore environmental data</h2></div><span className="section-subtext">Select cities, dates and a metric</span></div>
          <form onSubmit={applyFilters} className="filters-card">
            <div className="filter-field"><label htmlFor="city-one">Primary city</label><select id="city-one" value={filters.first} disabled={!catalog.datasets.length} onChange={(e) => changeCity("first", e.target.value)}>{catalog.datasets.map((item) => <option key={item.city} value={item.city} disabled={item.city === filters.second}>{cityLabel(item.city)}</option>)}</select></div>
            <div className="filter-field"><label htmlFor="city-two">Compare with</label><select id="city-two" value={filters.second} disabled={!catalog.datasets.length} onChange={(e) => changeCity("second", e.target.value)}><option value="">No comparison</option>{catalog.datasets.map((item) => <option key={item.city} value={item.city} disabled={item.city === filters.first}>{cityLabel(item.city)}</option>)}</select></div>
            <div className="filter-field"><label htmlFor="from-date">From</label><input id="from-date" type="date" value={filters.start} min={coverage?.start} max={coverage?.end} onChange={(e) => setFilters((prev) => ({ ...prev, start: e.target.value }))}/></div>
            <div className="filter-field"><label htmlFor="to-date">To</label><input id="to-date" type="date" value={filters.end} min={coverage?.start} max={coverage?.end} onChange={(e) => setFilters((prev) => ({ ...prev, end: e.target.value }))}/></div>
            <div className="filter-field metric-field"><label htmlFor="metric">Metric</label><select id="metric" value={filters.metric} onChange={(e) => setFilters((prev) => ({ ...prev, metric: e.target.value }))}>{Object.entries(METRICS).map(([key, metric]) => <option key={key} value={key}>{metric.short}</option>)}</select></div>
            <button className="btn btn-primary apply-btn" type="submit" disabled={!ready || (busy && !dirty)}><Icon name="arrowRight" size={17}/>Apply</button>
            <div className="form-note" role="status">{validation ? <span className="validation-message"><Icon name="alert" size={14}/>{validation}</span> : <span><Icon name="calendar" size={14}/>{dayCount(filters.start, filters.end)} days selected · Maximum 31</span>}</div>
          </form>
        </section>
        <div className="section-heading compact"><div><span className="section-kicker">03 / SNAPSHOT</span><h2>Period highlights</h2></div><span className="section-subtext">{applied?.first ? `${cityLabel(applied.first)} · ${formatDate(applied.start)} – ${formatDate(applied.end)}` : "Choose a valid period"}</span></div>
        <div className="stats-row">
          <SummaryTile icon="thermometer" label="Avg. max temperature" value={observations.loading ? "…" : formatValue(meanValue(observationRows, "temp_max_c"), "°C")} footer="Daily maximum · selected period" accent="temp"/>
          <SummaryTile icon="activity" label="Avg. min temperature" value={observations.loading ? "…" : formatValue(meanValue(observationRows, "temp_min_c"), "°C")} footer="Daily minimum · selected period" accent="min"/>
          <SummaryTile icon="droplet" label="Total precipitation" value={observations.loading ? "…" : formatValue(sumValue(observationRows, "precipitation_mm"), "mm")} footer="Accumulated over selected period" accent="rain"/>
          <SummaryTile icon="shield" label="Retrieval integrity" value={observations.loading || comparison.loading ? "Checking…" : checked || (observations.data?.sha256_verified && !applied?.second) ? "Verified" : "Not verified"} footer="SHA-256 checks from the backend" accent="integrity"/>
        </div>
        {observations.error && <StatusPanel title="Observations could not be retrieved" description={observations.error.message} code={observations.error.code} retry={() => setApplied(applied ? { ...applied } : null)}/>}
        <section className="content-card comparison-card" id="comparison">
          <div className="panel-header"><div><span className="section-kicker">04 / CROSS-REGION ANALYSIS</span><h2>Region comparison</h2><p>{applied?.second ? `${cityLabel(applied.first)} vs. ${cityLabel(applied.second)} · ${METRICS[applied.metric]?.title}` : "Select a second city to compare regional datasets."}</p></div>
            <button className="btn btn-outlined" type="button" disabled={!compareData?.points?.length || comparison.loading} onClick={() => exportCSV(compareData, applied)}><Icon name="download" size={17}/>Export CSV</button></div>
          {comparison.loading ? <div className="skeleton chart-skeleton"/> : comparison.error ? <StatusPanel title="Comparison unavailable" description={comparison.error.message} code={comparison.error.code} retry={() => setApplied(applied ? { ...applied } : null)}/> : compareData ? <SeriesChart data={compareData} firstName={compareData.city1} secondName={compareData.city2} /> : <div className="empty-state"><Icon name="chart" size={34}/><p>Select two cities and apply a valid date range to compare their observations.</p></div>}
          <div className="panel-footer"><Icon name="shield" size={15}/><span>Source locations and SHA-256 validation come from the federated API. Values are never fabricated in the browser.</span></div>
        </section>
        <div className="lower-row">
          <section className="content-card table-panel" id="observations">
            <div className="panel-header tight"><div><span className="section-kicker">05 / RAW OBSERVATIONS</span><h2>Daily readings</h2><p>{applied?.first ? cityLabel(applied.first) : "Primary city"} · {observations.data?.row_count ?? 0} loaded rows</p></div></div>
            {observations.loading ? <div className="skeleton rows-skeleton"/> : observationRows.length ? <div className="table-scroll"><table><thead><tr><th>Date</th><th>Max temp</th><th>Min temp</th><th>Rainfall</th></tr></thead><tbody>{observationRows.map((item) => <tr key={item.date}><td>{formatDate(item.date, { day: "numeric", month: "short" })}</td><td>{formatValue(item.temp_max_c, "°C")}</td><td>{formatValue(item.temp_min_c, "°C")}</td><td>{formatValue(item.precipitation_mm, "mm")}</td></tr>)}</tbody></table></div> : <div className="empty-state short">No observations to display.</div>}
          </section>
          <section className="content-card provenance-card">
            <div className="panel-header tight"><div><span className="section-kicker">06 / DATA TRUST</span><h2>Source provenance</h2><p>Know where your data comes from.</p></div></div>
            <div className="provenance-list">
              <div><span className="provenance-icon"><Icon name="globe" size={17}/></span><section><small>Data source</small><strong>{observations.data?.source || "Awaiting S3 retrieval"}</strong></section></div>
              <div><span className="provenance-icon"><Icon name="server" size={17}/></span><section><small>Primary AWS region</small><strong>{observations.data?.aws_region || "—"}</strong></section></div>
              <div><span className="provenance-icon"><Icon name="shield" size={17}/></span><section><small>Dataset integrity</small><strong>{observations.data?.sha256_verified === true ? "SHA-256 verified" : "Not verified"}</strong></section></div>
              <div><span className="provenance-icon"><Icon name="calendar" size={17}/></span><section><small>Published data range</small><strong>{observations.data ? `${formatDate(observations.data.requested_start)} – ${formatDate(observations.data.requested_end)}` : "—"}</strong></section></div>
            </div>
            <div className="security-note"><Icon name="info" size={16}/><span>Private bucket names and AWS keys are never sent to the frontend.</span></div>
          </section>
        </div>
        <footer className="site-footer"><span>© EnviroSync · Modular environmental data federation</span><span>Powered by FastAPI, React and AWS S3</span></footer>
      </div>
    </main>
  </div>;
}
