import React from "react";
import Icon from "./Icon.jsx";

export default function StatusPanel({ title, description, code, retry, type = "error" }) {
  return <div className={`status-panel status-${type}`} role={type === "error" ? "alert" : "status"}>
    <div className="status-symbol"><Icon name={type === "error" ? "alert" : "info"} size={23} /></div>
    <div className="status-content">
      <strong>{title}</strong>
      <p>{description}</p>
      {code && <code>{code}</code>}
    </div>
    {retry && <button className="btn btn-soft btn-small" type="button" onClick={retry}><Icon name="refresh" size={15} /> Retry</button>}
  </div>;
}
