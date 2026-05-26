// Voortgang-store. Default: localStorage. Als /api/learn/progress beschikbaar
// is (zie fase 6) syncen we ernaartoe; tot die tijd is alles puur client.
//
// Sleutel-structuur: `${role}/${level}/${order}` met status 'done'|'in-progress'.
// Quiz-antwoorden en check-resultaten vallen onder dezelfde sleutels.

export type ModuleStatus = 'done' | 'in-progress';
export type ProgressMap = Record<string, ModuleStatus>;

const LS_KEY = 'odap-learn-progress';
const SYNC_URL = '/api/learn/progress';
let cache: ProgressMap | null = null;
let syncAvailable: boolean | null = null;

export function readProgress(): ProgressMap {
  if (cache) return cache;
  try {
    const raw = localStorage.getItem(LS_KEY);
    cache = raw ? (JSON.parse(raw) as ProgressMap) : {};
  } catch {
    cache = {};
  }
  return cache!;
}

export function setProgress(key: string, status: ModuleStatus): void {
  const p = readProgress();
  p[key] = status;
  cache = p;
  try { localStorage.setItem(LS_KEY, JSON.stringify(p)); } catch {}
  void trySync(p);
  // Notify rest van pagina (eigen event, geen storage-event nodig).
  document.dispatchEvent(new CustomEvent('odap-learn:progress', { detail: p }));
}

export function clearProgress(): void {
  cache = {};
  try { localStorage.removeItem(LS_KEY); } catch {}
  void trySync({});
  document.dispatchEvent(new CustomEvent('odap-learn:progress', { detail: {} }));
}

export function statusOf(key: string): ModuleStatus | undefined {
  return readProgress()[key];
}

// ─── Voortgang renderen op alle ProgressDot-elementen op de pagina ───
export function renderDots(): void {
  const p = readProgress();
  document.querySelectorAll<HTMLElement>('[data-progress-key]').forEach((el) => {
    const k = el.dataset.progressKey!;
    el.classList.remove('done', 'in-progress');
    const s = p[k];
    if (s) el.classList.add(s);
  });
  document.querySelectorAll<HTMLElement>('[data-track-progress]').forEach((el) => {
    const role = el.closest<HTMLElement>('[data-track-role]')?.dataset.trackRole;
    if (!role) return;
    const total = Number(el.textContent?.split('/')[1] ?? 0);
    const done = Object.entries(p).filter(([k, v]) => k.startsWith(role + '/') && v === 'done').length;
    el.textContent = `${done}/${total}`;
  });
}

// ─── Optionele sync naar de Astro-server-route (fase 6) ───
async function trySync(p: ProgressMap): Promise<void> {
  if (syncAvailable === false) return;
  try {
    const r = await fetch(SYNC_URL, {
      method: 'PUT',
      credentials: 'include',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ progress: p }),
    });
    syncAvailable = r.ok;
  } catch {
    syncAvailable = false;
  }
}

export async function pullRemote(): Promise<void> {
  try {
    const r = await fetch(SYNC_URL, { credentials: 'include' });
    if (!r.ok) { syncAvailable = false; return; }
    const j = (await r.json()) as { progress?: ProgressMap };
    if (j.progress) {
      cache = j.progress;
      try { localStorage.setItem(LS_KEY, JSON.stringify(cache)); } catch {}
      renderDots();
      syncAvailable = true;
    }
  } catch {
    syncAvailable = false;
  }
}

// ─── Bootstrap (auto-aangeroepen vanuit elke Learn-pagina) ───
export function bootstrap(): void {
  if (typeof document === 'undefined') return;
  void pullRemote().finally(renderDots);
  document.addEventListener('odap-learn:progress', renderDots as EventListener);
}
