/*
  PowerBIEmbed — React Island for the portal-shell.

  Rendert een Power BI rapport binnen het v2-shell-frame:
    1. GET /api/portal/powerbi/reports — workspace report-lijst voor de
       dropdown bovenaan.
    2. POST /api/portal/powerbi/embed/<reportId> — krijgt een embed-token
       gegrond on the gefedereerde Entra-identity van de portal-user
       (via oauth2-proxy + Keycloak↔Entra broker, ADR-0008).
    3. Render <PowerBIEmbed config={...}> uit powerbi-client-react.
    4. Handle loading + error states; auto-refresh token bij expiry.

  State-persistence: gekozen report-ID leeft in URL ?report=<id> én
  localStorage (`odap-portal:powerbi:selectedReportId`) zodat refresh hetzelfde
  rapport opent. URL wint van localStorage wint van de explicit selection.

  Identity-toggle: ?identity=on triggert {effectiveIdentity:true} in de
  embed-token-mint, zodat RLS-rules op USERNAME() de gefedereerde
  Entra-email zien. Required een fixed-identity-cloud-connection op het
  semantic model — zonder die geeft Power BI 403 (zie use-case-doc).

  Geen MSAL.js in de browser — de embed-token komt vanuit de portal-backend,
  de Entra-tokens van de user worden alleen in Keycloak gehouden. Dit is de
  App-Owns-Data-met-effective-identity flow, niet pure User-Owns-Data.
*/
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { PowerBIEmbed as PowerBIEmbedRC } from "powerbi-client-react";
import { models } from "powerbi-client";
import type { Report } from "powerbi-client";

interface Props {
  /** Power BI report-ID — overrule de auto-resolve uit URL/storage. */
  reportId?: string;
  /** Optionele page-naam binnen het report. */
  pageName?: string;
}

interface EmbedConfig {
  embedUrl:    string;
  accessToken: string;
  expiration:  string;
  reportId:    string;
  datasetId:   string;
}

interface ReportInfo {
  id:        string;
  name:      string;
  datasetId: string | null;
  embedUrl:  string | null;
  webUrl:    string | null;
}

interface ReportsResponse {
  workspace_id: string;
  reports:      ReportInfo[];
}

// Optional integration: an operator/user must explicitly choose a report.
const DEFAULT_REPORT_ID = "";
const LAST_REPORT_LS_KEY = "odap-portal:powerbi:selectedReportId";


// ─── Backend helpers ──────────────────────────────────────────────────
async function fetchReportsList(): Promise<ReportsResponse> {
  const resp = await fetch("/api/portal/powerbi/reports", { credentials: "include" });
  if (!resp.ok) {
    const txt = await resp.text();
    throw new Error(`reports (${resp.status}): ${txt.slice(0, 240)}`);
  }
  return await resp.json();
}

async function fetchEmbedConfig(reportId: string, identity: boolean): Promise<EmbedConfig> {
  const resp = await fetch(`/api/portal/powerbi/embed/${reportId}`, {
    method:      "POST",
    credentials: "include",
    headers:     { "Content-Type": "application/json" },
    body:        JSON.stringify(identity ? { effectiveIdentity: true } : {}),
  });
  if (!resp.ok) {
    const txt = await resp.text();
    throw new Error(`embed-token (${resp.status}): ${txt.slice(0, 240)}`);
  }
  return await resp.json();
}


// ─── URL / storage helpers ────────────────────────────────────────────
function urlParam(name: string): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get(name);
}

function syncUrlParam(name: string, value: string | null): void {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  if (value) url.searchParams.set(name, value);
  else       url.searchParams.delete(name);
  // replaceState — geen extra history-entry per dropdown-keuze.
  window.history.replaceState({}, "", url.toString());
}

function storedLastReport(): string | null {
  if (typeof window === "undefined") return null;
  try { return window.localStorage.getItem(LAST_REPORT_LS_KEY); }
  catch { return null; }
}

function rememberLastReport(id: string): void {
  if (typeof window === "undefined") return;
  try { window.localStorage.setItem(LAST_REPORT_LS_KEY, id); } catch { /* no-op */ }
}


export default function PowerBIEmbed({ reportId: propReportId, pageName }: Props): JSX.Element {
  // Initiële report-keuze: prop → URL → localStorage → explicit selection.
  const initialReportId = useMemo<string>(
    () => propReportId ?? urlParam("report") ?? storedLastReport() ?? DEFAULT_REPORT_ID,
    [propReportId],
  );
  const initialIdentity = useMemo<boolean>(
    () => (urlParam("identity") ?? "").toLowerCase() === "on",
    [],
  );

  const [reports, setReports]               = useState<ReportInfo[]>([]);
  const [reportsErr, setReportsErr]         = useState<string | null>(null);
  const [selectedReportId, setSelectedId]   = useState<string>(initialReportId);
  const [identityMode, setIdentityMode]     = useState<boolean>(initialIdentity);
  const [cfg, setCfg]                       = useState<EmbedConfig | null>(null);
  const [err, setErr]                       = useState<string | null>(null);
  const reportRef                           = useRef<Report | null>(null);

  // Reports-lijst eenmaal ophalen bij mount.
  useEffect(() => {
    let cancelled = false;
    fetchReportsList()
      .then((r) => {
        if (cancelled) return;
        setReports(r.reports);
        // Als de geselecteerde report-ID niet in de lijst zit, fallback
        // to the eerste; behoudt geen "ghost" selectie na een delete.
        if (r.reports.length > 0 && !r.reports.some((x) => x.id === selectedReportId)) {
          setSelectedId("");
        }
      })
      .catch((e) => { if (!cancelled) setReportsErr(String(e?.message ?? e)); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount-only fetch
  }, []);

  // Persist + sync URL als selectie of identity-mode wijzigt.
  useEffect(() => {
    rememberLastReport(selectedReportId);
    syncUrlParam("report", selectedReportId);
  }, [selectedReportId]);
  useEffect(() => {
    syncUrlParam("identity", identityMode ? "on" : null);
  }, [identityMode]);

  // Embed-config ophalen telkens als (report, identity) wijzigt.
  useEffect(() => {
    let cancelled = false;
    setCfg(null);
    setErr(null);
    if (!selectedReportId) return;
    fetchEmbedConfig(selectedReportId, identityMode)
      .then((c) => { if (!cancelled) setCfg(c); })
      .catch((e) => { if (!cancelled) setErr(String(e?.message ?? e)); });
    return () => { cancelled = true; };
  }, [selectedReportId, identityMode]);

  // Token-refresh — embed-tokens leven max 60min. We refreshen 5min vóór
  // expiry zodat lange sessies geen onderbreking krijgen.
  useEffect(() => {
    if (!cfg?.expiration) return;
    const expiresAt = new Date(cfg.expiration).getTime();
    const refreshIn = Math.max(60_000, expiresAt - Date.now() - 5 * 60_000);
    const t = window.setTimeout(async () => {
      try {
        const next = await fetchEmbedConfig(selectedReportId, identityMode);
        setCfg(next);
        // Geef de nieuwe token aan de embed zonder remount.
        await reportRef.current?.setAccessToken(next.accessToken);
      } catch (e) {
        console.warn("powerbi: token-refresh faalde", e);
      }
    }, refreshIn);
    return () => window.clearTimeout(t);
  }, [cfg?.expiration, selectedReportId, identityMode]);

  const onReportChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedId(e.target.value);
  }, []);

  const onIdentityToggle = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setIdentityMode(e.target.checked);
  }, []);

  // Selecteer/render-prep: pageNavigation onderaan blijft, filters dichtgeklapt.
  const embedSettings = useMemo(() => ({
    panes: {
      filters:        { visible: false, expanded: false },
      pageNavigation: { visible: true, position: models.PageNavigationPosition.Bottom },
    },
    background: models.BackgroundType.Transparent,
    layoutType: models.LayoutType.Custom,
    customLayout: { displayOption: models.DisplayOption.FitToPage },
  }), []);

  return (
    <div className="pbi-shell">
      <Toolbar
        reports={reports}
        reportsErr={reportsErr}
        selectedId={selectedReportId}
        onReportChange={onReportChange}
        identityMode={identityMode}
        onIdentityToggle={onIdentityToggle}
      />
      <div className="pbi-wrap">
        {!selectedReportId ? (
          <div className="pbi-loading"><p>Power BI is optional. Choose a configured job-market report, or <a href="/job-market/">open the Dutch IT job-market explorer</a>.</p></div>
        ) : err ? (
          <PowerBIErrorPanel err={err} reportId={selectedReportId} />
        ) : !cfg ? (
          <div className="pbi-loading" aria-live="polite">
            <span className="pbi-spinner" aria-hidden="true" />
            <span>Power BI rapport laden…</span>
          </div>
        ) : (
          <PowerBIEmbedRC
            embedConfig={{
              type:        "report",
              id:          cfg.reportId,
              embedUrl:    cfg.embedUrl,
              accessToken: cfg.accessToken,
              tokenType:   models.TokenType.Embed,
              pageName,
              settings:    embedSettings,
            }}
            eventHandlers={
              new Map<string, (evt?: unknown) => void>([
                ["loaded",   () => console.info("powerbi: report loaded")],
                ["rendered", () => console.info("powerbi: report rendered")],
                ["error",    (evt) => {
                  console.error("powerbi: error", evt);
                  setErr(`Power BI runtime error — zie console.`);
                }],
              ])
            }
            getEmbeddedComponent={(embed) => {
              reportRef.current = embed as Report;
            }}
            cssClassName="pbi-frame"
          />
        )}
      </div>
      <PowerBIStyles />
    </div>
  );
}


// ─── Toolbar ──────────────────────────────────────────────────────────
function Toolbar(props: {
  reports:          ReportInfo[];
  reportsErr:       string | null;
  selectedId:       string;
  onReportChange:   (e: React.ChangeEvent<HTMLSelectElement>) => void;
  identityMode:     boolean;
  onIdentityToggle: (e: React.ChangeEvent<HTMLInputElement>) => void;
}): JSX.Element {
  const { reports, reportsErr, selectedId, onReportChange, identityMode, onIdentityToggle } = props;
  const hasList    = reports.length > 0;
  const inList     = hasList && reports.some((r) => r.id === selectedId);
  const reportName = reports.find((r) => r.id === selectedId)?.name;

  return (
    <header className="pbi-toolbar">
      <label className="pbi-toolbar-field">
        <span className="pbi-toolbar-label">Rapport</span>
        {reportsErr ? (
          <span className="pbi-toolbar-error" title={reportsErr}>
            kan reports niet laden
          </span>
        ) : !hasList ? (
          <span className="pbi-toolbar-muted">— laden…</span>
        ) : (
          <select
            className="pbi-select"
            value={inList ? selectedId : ""}
            onChange={onReportChange}
            aria-label="Kies een Power BI rapport"
          >
            {!inList && (
              <option value="" disabled>
                {reportName ?? "—"}
              </option>
            )}
            {reports.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
        )}
      </label>

      <label className="pbi-toolbar-field pbi-toolbar-toggle" title="Stuur de gefedereerde Entra-email mee als effectiveIdentity (vereist fixed-identity cloud connection on the semantic model)">
        <input
          type="checkbox"
          checked={identityMode}
          onChange={onIdentityToggle}
        />
        <span>Use my identity (RLS)</span>
      </label>
    </header>
  );
}


// ─── Error-panel ──────────────────────────────────────────────────────
function PowerBIErrorPanel({ err, reportId }: { err: string; reportId: string }): JSX.Element {
  return (
    <div className="pbi-fallback">
      <h2>Power BI laden faalde</h2>
      <p className="pbi-fallback-detail mono">{err}</p>
      <p>
        Controleer dat je bent ingelogd via Entra (Keycloak-broker), en dat
        de portal-backend de FABRIC_* env-vars heeft. Zie{" "}
        <code>docs/use-cases/dutch-it-job-market.md</code>.
      </p>
      <a
        className="pbi-fallback-link"
        href={`https://app.fabric.microsoft.com/groups/me/reports/${reportId}`}
        target="_blank"
        rel="noopener noreferrer"
      >
        Open direct op app.fabric.microsoft.com ↗
      </a>
    </div>
  );
}


// ─── Style ────────────────────────────────────────────────────────────
// Style-component in plaats van een externe .css zodat het Island self-
// contained blijft (cssClassName on the embed-component werkt zo ook out
// of the box in Astro's React-island context).
function PowerBIStyles(): JSX.Element {
  return (
    <style>{`
      .pbi-shell {
        /* parent is embed-frame-wrap (display:block) en astro-island
           (display:contents) — flex:1 erft niet door, dus expliciet
           height:100% van de wrap pakken. */
        display: flex; flex-direction: column; flex: 1;
        height: 100%; min-height: 0;
        background: var(--bg-sunken, #0c0c0c);
      }
      .pbi-toolbar {
        flex-shrink: 0; display: flex; align-items: center; gap: var(--space-3, 12px);
        padding: 6px 12px; background: var(--bg-elev, #161616);
        border-bottom: 1px solid var(--line, #2a2a2a);
        font-size: var(--text-meta, 13px); color: var(--ink-1, #ededed);
        min-height: 40px;
      }
      .pbi-toolbar-field {
        display: inline-flex; align-items: center; gap: 8px;
      }
      .pbi-toolbar-label {
        color: var(--ink-3, #888); font-size: var(--text-micro, 12px);
        text-transform: uppercase; letter-spacing: 0.04em;
      }
      .pbi-toolbar-muted { color: var(--ink-3, #888); font-style: italic; }
      .pbi-toolbar-error { color: var(--accent-danger, #c45151); font-style: italic; }
      .pbi-toolbar-toggle {
        margin-left: auto; cursor: pointer; user-select: none;
        color: var(--ink-2, #cfcfcf);
      }
      .pbi-toolbar-toggle input { accent-color: var(--accent, #c4451c); cursor: pointer; }
      .pbi-select {
        background: var(--bg, #1a1a1a); color: var(--ink-1, #ededed);
        border: 1px solid var(--line, #2a2a2a); border-radius: 4px;
        padding: 4px 8px; font-size: var(--text-meta, 13px); min-width: 240px;
        font-family: var(--font-sans, system-ui, sans-serif);
      }
      .pbi-select:focus { outline: 2px solid var(--accent, #c4451c); outline-offset: 1px; }

      .pbi-wrap { display: flex; flex: 1; min-height: 0; }
      .pbi-frame, .pbi-frame > iframe { width: 100%; height: 100%; border: 0; }

      .pbi-loading {
        flex: 1; display: flex; align-items: center; justify-content: center;
        gap: 12px; color: var(--ink-3, #888); font-size: var(--text-meta, 13px);
      }
      .pbi-spinner {
        width: 14px; height: 14px; border: 2px solid var(--ink-4, #444);
        border-top-color: var(--accent, #c4451c); border-radius: 50%;
        animation: pbi-spin 0.8s linear infinite;
      }
      @keyframes pbi-spin { to { transform: rotate(360deg); } }

      .pbi-fallback {
        margin: auto; max-width: 520px;
        background: var(--bg-elev, #161616); border: 1px solid var(--line, #2a2a2a);
        border-radius: 8px; padding: 24px; display: grid; gap: 12px;
        color: var(--ink-1, #ededed); font-size: var(--text-meta, 13px);
      }
      .pbi-fallback h2 { margin: 0; font-size: 16px; }
      .pbi-fallback-detail {
        font-family: var(--font-mono, ui-monospace, SFMono-Regular, monospace);
        color: var(--ink-3, #888); font-size: 12px;
        background: var(--bg-sunken, #0a0a0a); padding: 8px 10px; border-radius: 4px;
        white-space: pre-wrap; word-break: break-word;
      }
      .pbi-fallback-link {
        display: inline-block; margin-top: 6px;
        color: var(--accent, #c4451c); text-decoration: none; font-weight: 500;
      }
      .pbi-fallback-link:hover { text-decoration: underline; }
    `}</style>
  );
}
