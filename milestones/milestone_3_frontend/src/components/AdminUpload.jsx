import React, { useState } from "react";
import { adminConfigured, beginAdminSignIn, signOutAdmin } from "../lib/admin.mjs";
import { createApi } from "../lib/api.mjs";

const api = createApi(import.meta.env.VITE_API_BASE_URL || "");
const MAX_SIZE = 200_000;

function encodeFile(bytes) {
  let parts = "";
  for (const byte of bytes) parts += String.fromCharCode(byte);
  return btoa(parts);
}

export default function AdminUpload({ accessToken, expiresAt, authError, onUploaded, onSignOut }) {
  const [file, setFile] = useState(null);
  const [city, setCity] = useState("");
  const [country, setCountry] = useState("");
  const [source, setSource] = useState("");
  const [region, setRegion] = useState("ap-south-1");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [isError, setIsError] = useState(false);
  const signedIn = Boolean(accessToken && Date.now() < expiresAt);

  async function submit(event) {
    event.preventDefault();
    if (!signedIn || !file || busy) return;
    setFeedback("");
    setIsError(false);
    if (file.size > MAX_SIZE) {
      setFeedback("File exceeds 200 KB. Upload a smaller dataset.");
      setIsError(true);
      return;
    }
    setBusy(true);
    try {
      const raw = await file.arrayBuffer();
      const result = await api.uploadDataset({
        city: city.trim().toLowerCase(),
        country: country.trim(),
        source: source.trim(),
        region,
        filename: file.name,
        file_base64: encodeFile(new Uint8Array(raw)),
      }, accessToken);
      setFeedback(`Registered ${result.dataset.city} (${result.dataset.observation_count} days). SHA-256: ${result.dataset.sha256.slice(0, 14)}…`);
      setFile(null);
      setCity("");
      setCountry("");
      setSource("");
      const input = document.getElementById("admin-csv-json");
      if (input) input.value = "";
      onUploaded();
    } catch (error) {
      setIsError(true);
      setFeedback(error.message || "Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  return <section className="admin-upload" id="admin-upload" aria-labelledby="admin-upload-title">
    <header className="admin-upload-head">
      <div><span className="section-kicker">ADMINISTRATOR / DATA INGESTION</span><h2 id="admin-upload-title">Publish a new dataset</h2><p>CSV or JSON historical daily observations; two approved AWS regions. Existing ERA5 datasets are preserved.</p></div>
      {signedIn ? <button className="btn btn-outlined" type="button" onClick={() => { onSignOut(); signOutAdmin(); }}>Sign out</button> : adminConfigured ? <button className="btn btn-primary" type="button" onClick={() => beginAdminSignIn().catch(e => { setIsError(true); setFeedback(e.message); })}>Administrator sign in</button> : <span className="admin-disabled">Uploads not configured</span>}
    </header>
    {authError && <p className="admin-feedback error" role="alert">{authError}</p>}
    {signedIn && <form className="admin-upload-form" onSubmit={submit}>
      <label>City identifier <small>(new city, lowercase; e.g. berlin)</small><input required maxLength={30} minLength={3} pattern="[a-z][a-z0-9-]{2,29}" value={city} onChange={e => setCity(e.target.value)} placeholder="berlin" /></label>
      <label>Country<input required maxLength={60} value={country} onChange={e => setCountry(e.target.value)} placeholder="Germany" /></label>
      <label>Source attribution<input required maxLength={120} value={source} onChange={e => setSource(e.target.value)} placeholder="Local monitoring station" /></label>
      <label>Storage region<select value={region} onChange={e => setRegion(e.target.value)}><option value="ap-south-1">Mumbai — ap-south-1</option><option value="eu-west-2">London — eu-west-2</option></select></label>
      <label>Dataset file (.csv or .json, ≤ 200 KB)<input id="admin-csv-json" type="file" accept=".csv,.json,text/csv,application/json" required onChange={e => setFile(e.target.files?.[0] || null)} /></label>
      <p className="admin-schema">CSV columns: <code>date,temp_max_c,temp_min_c,precipitation_mm</code>. JSON: an array of these row objects. Dates must be consecutive YYYY-MM-DD, up to 366 days. Temperatures are °C and rainfall is mm.</p>
      <button className="btn btn-primary" disabled={!file || busy} type="submit">{busy ? "Validating and publishing…" : "Validate and publish"}</button>
    </form>}
    {feedback && <p className={`admin-feedback ${isError ? "error" : "success"}`} role="status">{feedback}</p>}
    {!signedIn && <p className="admin-schema">The public dashboard remains read-only. Only Cognito administrators can publish data. Access tokens stay in browser memory and are never saved in local storage.</p>}
  </section>;
}
