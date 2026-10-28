import { useEffect, useMemo, useState } from 'react';

type Job = {
  job_id: string; duplicate_group_id: string; snapshot_date: string; title: string; company: string | null;
  city: string | null; province: string | null; source: string; sources?: string[];
  domains: string[]; skills: string[]; work_mode: string | null; is_synthetic: boolean;
  salary_min: number | null; salary_max: number | null; salary_currency: string | null;
  salary_period: string | null; salary_year_min: number | null; salary_year_max: number | null;
  salary_is_estimated: boolean; employment_type: string | null; contract_type: string | null;
  hours_min: number | null; hours_max: number | null; seniority: string | null;
  language: string | null; education: string | null; published_at: string | null;
  expires_at: string | null; observed_at: string; canonical_url: string; description_text: string;
  source_job_id: string; country_code: string; latitude: number | null; longitude: number | null;
  source_observations?: number;
};
const number = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 0 });
const text = (value: unknown) => value === null || value === undefined || value === '' ? 'Unknown' : String(value).replaceAll('_', ' ');
const domains = ['Data', 'Cloud', 'SAP', 'AI', 'Software', 'Security'];
function originalSalary(job: Job): string {
  if (job.salary_min == null && job.salary_max == null) return 'Salary not supplied';
  return `${job.salary_currency ?? '?'} ${job.salary_min == null ? '?' : number.format(job.salary_min)}–${job.salary_max == null ? '?' : number.format(job.salary_max)} / ${job.salary_period ?? 'unknown period'} · ${job.salary_is_estimated ? 'estimated' : 'reported'}`;
}
function deduplicate(input: Job[]): Job[] {
  const groups = new Map<string, Job[]>();
  for (const job of input) { const key = `${job.snapshot_date}:${job.duplicate_group_id}`; groups.set(key, [...(groups.get(key) ?? []), job]); }
  const quality = (j: Job) => [j.salary_min, j.salary_max, j.city, j.description_text, j.language, j.education].filter(v => v != null && v !== '').length;
  return [...groups.values()].map(group => ({
    ...[...group].sort((a, b) => quality(b) - quality(a) || a.job_id.localeCompare(b.job_id))[0],
    domains: [...new Set(group.flatMap(j => j.domains))], skills: [...new Set(group.flatMap(j => j.skills))],
    sources: [...new Set(group.flatMap(j => j.sources ?? [j.source]))], source_observations: group.reduce((n, j) => n + (j.source_observations ?? 1), 0),
  }));
}
function readDataset(value: unknown): Job[] {
  const obj = value as { observations?: unknown; listings?: unknown };
  const input = Array.isArray(value) ? value : obj?.observations ?? obj?.listings;
  if (!Array.isArray(input) || !input.length) throw new Error('No normalized observations or dashboard listings found.');
  const valid = input.every(j => j && typeof j === 'object' && typeof j.snapshot_date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(j.snapshot_date) &&
    typeof j.job_id === 'string' && typeof j.duplicate_group_id === 'string' && typeof j.title === 'string' && (j.company === null || typeof j.company === 'string') && typeof j.source === 'string' &&
    typeof j.is_synthetic === 'boolean' && Array.isArray(j.domains) && j.domains.every((d: unknown) => typeof d === 'string') && Array.isArray(j.skills) && j.skills.every((s: unknown) => typeof s === 'string'));
  if (!valid) throw new Error('Use the generated dashboard.json or normalized observation records. Required job fields are missing.');
  if (new Set(input.map(j => j.is_synthetic)).size > 1) throw new Error('Explore synthetic and live observations separately.');
  return input as Job[];
}
function safeUrl(value: string): string | undefined {
  try { const u = new URL(value); return ['http:', 'https:'].includes(u.protocol) ? u.href : undefined; } catch { return undefined; }
}
function JobCard({ job }: { job: Job }) {
  const fields: [string, unknown][] = [
    ['Seniority', job.seniority], ['Employment type', job.employment_type], ['Contract', job.contract_type],
    ['Hours per week', job.hours_min == null && job.hours_max == null ? null : `${job.hours_min ?? '?'}–${job.hours_max ?? '?'}`],
    ['Skills', job.skills.join(', ')], ['Language', job.language], ['Education', job.education],
    ['Province / country', [job.province, job.country_code].filter(Boolean).join(', ')],
    ['Coordinates', job.latitude == null || job.longitude == null ? null : `${job.latitude}, ${job.longitude}`],
    ['Original salary', originalSalary(job)], ['Annual EUR minimum', job.salary_year_min], ['Annual EUR maximum', job.salary_year_max],
    ['Source salary estimate', job.salary_is_estimated ? 'Yes' : 'No'], ['Published', job.published_at], ['Expires', job.expires_at],
    ['Observed at (UTC)', job.observed_at], ['Snapshot date', job.snapshot_date], ['Sources', (job.sources ?? [job.source]).join(', ')],
    ['Source observations', job.source_observations ?? 1], ['Original source ID', job.source_job_id], ['Stable source job ID', job.job_id],
    ['Duplicate group', job.duplicate_group_id], ['Synthetic', job.is_synthetic ? 'Yes' : 'No'],
  ];
  return <details className="job-card"><summary><div><h3>{job.title}</h3><p>{text(job.company)} · {text(job.city)} · {text(job.work_mode)}</p><div className="tags">{job.domains.map(d => <span key={d}>{d}</span>)}</div></div><span className="salary">{originalSalary(job)}</span></summary>
    <p>{job.description_text || 'Description not supplied.'}</p>
    <dl>{fields.map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{text(value)}</dd></div>)}</dl>
    {!job.is_synthetic && safeUrl(job.canonical_url) && <a href={safeUrl(job.canonical_url)} target="_blank" rel="noopener noreferrer">View the original job ↗</a>}
    <p className="small source-url">Source URL: {job.canonical_url}</p>
  </details>;
}
export default function JobMarketExplorer() {
  const [rows, setRows] = useState<Job[]>([]), [label, setLabel] = useState('Loading the synthetic sample…');
  const [snapshot, setSnapshot] = useState(''), [domain, setDomain] = useState(''), [city, setCity] = useState(''), [work, setWork] = useState(''), [query, setQuery] = useState('');
  const [error, setError] = useState('');
  function load(value: unknown, name: string) { const next = readDataset(value); setRows(next); setSnapshot([...new Set(next.map(j => j.snapshot_date))].sort().at(-1)!); setLabel(name); setError(''); setCity(''); }
  useEffect(() => { fetch('/job-market-demo.json').then(r => { if (!r.ok) throw new Error('Unable to load the sample.'); return r.json(); }).then(v => load(v, 'Seven daily snapshots ending 28 October 2026')).catch(e => setError(String(e))); }, []);
  const snapshots = [...new Set(rows.map(j => j.snapshot_date))].sort();
  const jobsByDay = useMemo(() => deduplicate(rows).filter(j => (!domain || j.domains.includes(domain)) && (!city || j.city === city) && (!work || (j.work_mode ?? 'unknown') === work) && (!query || [j.title, j.company, ...j.skills].join(' ').toLocaleLowerCase().includes(query.toLocaleLowerCase()))), [rows, domain, city, work, query]);
  const jobs = jobsByDay.filter(j => j.snapshot_date === snapshot).sort((a, b) => a.title.localeCompare(b.title));
  const reported = jobs.filter(j => !j.salary_is_estimated && j.salary_year_min != null && j.salary_year_max != null);
  const midpoint = reported.length ? reported.reduce((n, j) => n + (j.salary_year_min! + j.salary_year_max!) / 2, 0) / reported.length : null;
  const stats = [[String(jobs.length), 'Distinct observed jobs'], [String(jobs.reduce((n, j) => n + (j.source_observations ?? 1), 0)), 'Source observations'], [String(new Set(jobs.map(j => j.company).filter(Boolean)).size), 'Employers'], [midpoint == null ? 'Unknown' : `€${number.format(midpoint)}`, `Mean annual midpoint · ${reported.length} reported EUR ranges`]];
  const counts = snapshots.map(day => jobsByDay.filter(j => j.snapshot_date === day).length);
  const skills = new Map<string, number>(); jobs.forEach(j => new Set(j.skills).forEach(s => skills.set(s, (skills.get(s) ?? 0) + 1)));
  const synthetic = rows.length > 0 && rows[0].is_synthetic;
  async function upload(file?: File) {
    if (!file) return;
    try { if (file.size > 15 * 1024 * 1024) throw new Error('Choose an export smaller than 15 MB.'); const content = await file.text(); load(file.name.endsWith('.jsonl') ? content.split(/\r?\n/).filter(l => l.trim()).map(l => JSON.parse(l)) : JSON.parse(content), file.name); }
    catch (e) { setError(e instanceof Error ? e.message : 'Unable to read the export.'); }
  }
  return <>
    <section className="sample-note" aria-label="Dataset status"><strong>{rows.length ? synthetic ? 'Synthetic sample' : 'Imported source observations' : 'Loading sample'} · {label}</strong>
      <p>{synthetic ? 'Fictional employers and job boards. These reproducible observations are not live vacancies.' : 'Inspect the source manifest, permissions and coverage before drawing market conclusions.'}</p>
      <label className="upload">Explore your own extraction <input type="file" accept=".json,.jsonl,application/json" onChange={e => void upload(e.target.files?.[0])} /></label>
      <p className="small">Load generated dashboard.json or normalized observations JSON/JSONL. Files are processed in this browser.</p>{error && <p role="alert">{error}</p>}
    </section>
    <section className="filters" aria-label="Filter vacancies">
      <label>Snapshot<select value={snapshot} onChange={e => setSnapshot(e.target.value)}>{[...snapshots].reverse().map(d => <option key={d}>{d}</option>)}</select></label>
      <label>Domain<select value={domain} onChange={e => setDomain(e.target.value)}><option value="">All six domains</option>{domains.map(d => <option key={d} value={d.toLowerCase()}>{d}</option>)}</select></label>
      <label>Location<select value={city} onChange={e => setCity(e.target.value)}><option value="">All cities</option>{[...new Set(rows.map(j => j.city).filter((c): c is string => typeof c === 'string' && Boolean(c)))].sort().map(c => <option key={c}>{c}</option>)}</select></label>
      <label>Work mode<select value={work} onChange={e => setWork(e.target.value)}><option value="">All work modes</option>{['hybrid', 'remote', 'onsite', 'unknown'].map(w => <option key={w} value={w}>{w}</option>)}</select></label>
      <label className="search">Search role, employer or skill<input type="search" placeholder="Python, SAP, security…" value={query} onChange={e => setQuery(e.target.value)} /></label>
    </section>
    <section className="job-stats" aria-live="polite">{stats.map(([value, name]) => <article key={name}><strong>{value}</strong><span>{name}</span></article>)}</section>
    <div className="analysis-grid"><section className="panel"><h2>Daily observed demand</h2><p className="small">Distinct vacancy groups for these filters. Absence does not establish closure.</p><div className="daily-chart">{snapshots.map((d, i) => <div key={d} className="day-bar"><strong>{counts[i]}</strong><div className="bar-fill" style={{ height: `${Math.max(2, counts[i] / Math.max(1, ...counts) * 105)}px` }} aria-label={`${d}: ${counts[i]} distinct jobs`} /><span>{d.slice(5)}</span></div>)}</div></section>
      <section className="panel"><h2>Skills in demand</h2><p className="small">A vacancy may mention several skills.</p><div className="skills-chart">{[...skills].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, 8).map(([s, c]) => <div key={s} className="skill-row"><span>{s}</span><strong>{c}</strong></div>)}</div></section></div>
    <section className="panel"><div className="section-head"><h2>Explore the vacancies</h2><span className="small">{jobs.length} jobs · {snapshot}</span></div><p className="small">Original salary units, estimates and unknowns stay visible. Open a role for all fields and source provenance.</p><div className="job-listings" aria-live="polite">{jobs.map(j => <JobCard key={j.duplicate_group_id} job={j} />)}{!jobs.length && <p>No observations match these filters.</p>}</div></section>
  </>;
}
