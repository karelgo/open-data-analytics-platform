/*
  CommandPalette — Cmd+K search modal as a React Island.

  Mounted by ShellLayout via <CommandPalette client:load />. Opens via:
    - Cmd+K / Ctrl+K (window-level keydown)
    - 'cmdk-open' custom event (dispatched by the topbar search button)

  Closes via Escape or click on the overlay.

  Keyboard navigation:
    - ↑ / ↓ to move selected
    - Enter to follow the link
    - Esc to close

  CSS lives in ShellLayout's <style is:global> (.cmdk-*) — we reuse those
  class names so styling stays in one place. The component returns null
  when closed, so it adds zero DOM in the idle state.

  Data flow (fase C):
    user types  →  200ms debounce  →  GET /api/portal/search?q=…  →
    backend aggregator (OpenMetadata + Airflow + Superset + Grafana)
    → grouped & rendered.
  Backend down or unreachable → empty state with a "kan geen verbinding"
  hint, so the palette gracefully degrades.
*/
import { useEffect, useMemo, useRef, useState } from 'react';

type CmdkType =
  | 'dashboard' | 'dag' | 'table' | 'notebook' | 'query' | 'pipeline';

type ServiceSlug =
  | 'airflow' | 'dbt' | 'grafana' | 'hive' | 'jupyter' | 'kafka'
  | 'keycloak' | 'minio' | 'multica' | 'nifi' | 'opa' | 'openmetadata'
  | 'opensearch' | 'powerbi' | 'prometheus' | 'spark' | 'superset' | 'trino';

interface CmdkItem {
  type: CmdkType;
  service: ServiceSlug;
  title: string;
  sub: string;
  href: string;
}

// Whitelist of recognised types — backend may return more, we drop anything
// we don't have a tile-tint for so the UI stays consistent.
const VALID_TYPES: ReadonlySet<string> = new Set<CmdkType>([
  'dashboard', 'dag', 'table', 'notebook', 'query', 'pipeline',
]);
const VALID_SERVICES: ReadonlySet<string> = new Set<ServiceSlug>([
  'airflow', 'dbt', 'grafana', 'hive', 'jupyter', 'kafka',
  'keycloak', 'minio', 'multica', 'nifi', 'opa', 'openmetadata',
  'opensearch', 'prometheus', 'spark', 'superset', 'trino',
]);

type FetchState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'ok'; items: CmdkItem[] }
  | { kind: 'error'; msg: string };

const TYPE_GROUP: Record<CmdkType, string> = {
  dashboard: 'Dashboards',
  dag:       'Workflows (DAGs)',
  table:     'Tabellen',
  notebook:  'Notebooks',
  query:     'Queries',
  pipeline:  'Pipelines',
};

// Order groups consistently, regardless of CMDK_DATA insertion order.
const TYPE_ORDER: CmdkType[] = ['dashboard', 'dag', 'table', 'notebook', 'query', 'pipeline'];

export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(0);
  const [state, setState] = useState<FetchState>({ kind: 'idle' });
  const inputRef = useRef<HTMLInputElement>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  // Debounced fetch — 200ms delay so we don't hammer the backend on
  // every keystroke. AbortController cancels stale requests so an
  // older response can't overwrite a newer one. Backend errors render
  // a friendly "kan geen verbinding maken" state.
  useEffect(() => {
    if (!open) return;
    const q = query.trim();
    if (q.length < 2) {
      setState({ kind: 'idle' });
      return;
    }
    setState({ kind: 'loading' });
    const ac = new AbortController();
    const handle = window.setTimeout(async () => {
      try {
        const res = await fetch(
          `/api/portal/search?q=${encodeURIComponent(q)}`,
          { credentials: 'include', signal: ac.signal },
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const raw: unknown[] = Array.isArray(data?.items) ? data.items : [];
        const items: CmdkItem[] = raw
          .filter((i): i is Record<string, unknown> => typeof i === 'object' && i !== null)
          .filter(
            (i) =>
              typeof i.type === 'string' && VALID_TYPES.has(i.type) &&
              typeof i.service === 'string' && VALID_SERVICES.has(i.service) &&
              typeof i.title === 'string' && typeof i.href === 'string',
          )
          .map((i) => ({
            type:    i.type as CmdkType,
            service: i.service as ServiceSlug,
            title:   String(i.title),
            sub:     typeof i.sub === 'string' ? i.sub : '',
            href:    String(i.href),
          }));
        setState({ kind: 'ok', items });
      } catch (err) {
        if (ac.signal.aborted) return;
        setState({
          kind: 'error',
          msg: 'Kan geen verbinding maken with the zoek-backend.',
        });
      }
    }, 200);
    return () => {
      window.clearTimeout(handle);
      ac.abort();
    };
  }, [query, open]);

  // Filter + group + flatten the result list. Keep a flat list for
  // keyboard navigation but render grouped headers.
  const items = state.kind === 'ok' ? state.items : [];
  const { groups, flat } = useMemo(() => {
    const groupMap = new Map<CmdkType, CmdkItem[]>();
    for (const m of items) {
      const arr = groupMap.get(m.type) ?? [];
      arr.push(m);
      groupMap.set(m.type, arr);
    }
    // Build ordered groups (limit 6 per group, like the legacy version).
    const orderedGroups: { type: CmdkType; items: CmdkItem[] }[] = [];
    const flatList: CmdkItem[] = [];
    for (const type of TYPE_ORDER) {
      const arr = groupMap.get(type);
      if (!arr || arr.length === 0) continue;
      const sliced = arr.slice(0, 6);
      orderedGroups.push({ type, items: sliced });
      flatList.push(...sliced);
    }
    return { groups: orderedGroups, flat: flatList };
  }, [items]);

  // Reset selected when results change.
  useEffect(() => {
    setSelected(0);
  }, [items, open]);

  // Auto-scroll selected item into view.
  useEffect(() => {
    if (!open || !resultsRef.current) return;
    const el = resultsRef.current.querySelector<HTMLElement>(
      `[data-cmdk-index="${selected}"]`,
    );
    el?.scrollIntoView({ block: 'nearest' });
  }, [selected, open]);

  // Focus the input whenever we open.
  useEffect(() => {
    if (open) requestAnimationFrame(() => inputRef.current?.focus());
    else setQuery('');
  }, [open]);

  // Global keyboard + external-event listeners.
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent): void {
      // Cmd+K / Ctrl+K toggles
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen((o) => !o);
        return;
      }
      if (!open) return;

      if (e.key === 'Escape') {
        e.preventDefault();
        setOpen(false);
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelected((s) => Math.min(s + 1, flat.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelected((s) => Math.max(s - 1, 0));
      } else if (e.key === 'Enter') {
        const target = flat[selected];
        if (target) {
          e.preventDefault();
          window.location.href = target.href;
        }
      }
    }

    function onOpenEvent(): void { setOpen(true); }

    document.addEventListener('keydown', onKeyDown);
    window.addEventListener('cmdk-open', onOpenEvent);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('cmdk-open', onOpenEvent);
    };
  }, [open, flat, selected]);

  if (!open) return null;

  // Build the flat-index lookup so each result row knows its position
  // in the keyboard-navigation order.
  let flatIndex = -1;

  return (
    <div className="cmdk" role="dialog" aria-modal="true" aria-label="Snelzoeken">
      <div className="cmdk-overlay" onClick={() => setOpen(false)} />
      <div className="cmdk-card" role="document">
        <div className="cmdk-input-row">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.3-4.3" />
          </svg>
          <input
            ref={inputRef}
            type="text"
            className="cmdk-input"
            placeholder="Zoek over dashboards, DAGs, tabellen, notebooks, queries…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoComplete="off"
            spellCheck={false}
          />
          <kbd className="topbarv2-kbd">esc</kbd>
        </div>

        <div className="cmdk-results" ref={resultsRef}>
          {state.kind === 'idle' && (
            <div className="cmdk-empty">
              <strong>Wat zoek je?</strong>
              <span>
                Type minimaal 2 letters. Zoekt in OpenMetadata (catalog),
                Airflow (DAGs) en Grafana (dashboards).
              </span>
            </div>
          )}
          {state.kind === 'loading' && (
            <div className="cmdk-empty">
              <span>Zoeken…</span>
            </div>
          )}
          {state.kind === 'error' && (
            <div className="cmdk-empty">
              <strong>{state.msg}</strong>
              <span>The portal backend is currently unreachable — try again in a few seconds.</span>
            </div>
          )}
          {state.kind === 'ok' && flat.length === 0 && (
            <div className="cmdk-empty">
              <strong>No results for "{query}"</strong>
              <span>Tip: try a DAG name, dashboard title, or <code>schema.table</code>.</span>
            </div>
          )}
          {state.kind === 'ok' && flat.length > 0 && groups.map((group) => (
            <div key={group.type} className="cmdk-group">
              <div className="cmdk-group-head">{TYPE_GROUP[group.type]}</div>
              {group.items.map((item) => {
                flatIndex += 1;
                const isSelected = flatIndex === selected;
                return (
                  <a
                    key={item.href}
                    className="cmdk-item"
                    href={item.href}
                    data-type={item.type}
                    data-cmdk-index={flatIndex}
                    data-cmdk-selected={isSelected ? 'true' : undefined}
                    onMouseEnter={() => setSelected(flatIndex)}
                  >
                    <span className="cmdk-item-brand">
                      <img
                        src={`/icons/brand/${item.service}.svg`}
                        alt=""
                        width={20}
                        height={20}
                        loading="lazy"
                      />
                    </span>
                    <span className="cmdk-item-body">
                      <span className="cmdk-item-title">{item.title}</span>
                      <span className="cmdk-item-sub">{item.sub}</span>
                    </span>
                    <kbd className="topbarv2-kbd">⏎</kbd>
                  </a>
                );
              })}
            </div>
          ))}
        </div>

        <div className="cmdk-foot">
          <span><kbd className="topbarv2-kbd">↑↓</kbd> bladeren</span>
          <span><kbd className="topbarv2-kbd">⏎</kbd> openen</span>
          <span><kbd className="topbarv2-kbd">esc</kbd> sluiten</span>
          <span className="cmdk-foot-meta">Live · OpenMetadata + Airflow + Grafana</span>
        </div>
      </div>
    </div>
  );
}
