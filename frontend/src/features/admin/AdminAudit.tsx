import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "../../lib/api";

type AuditRow = { id:string;actor_id:string;action:string;entity_type:string;entity_id:string;details:Record<string,unknown>;created_at:string };

export default function AdminAudit() {
  const query = useQuery({ queryKey:["admin-audit-log"], queryFn:()=>apiRequest<AuditRow[]>("/api/v1/admin/audit-logs?limit=100") });
  return <div className="space-y-5"><header><p className="text-xs font-bold uppercase tracking-widest text-leaf">Administrator</p><h2 className="mt-1 text-2xl font-semibold">Activity audit</h2><p className="mt-1 text-sm text-slate-500">Operational records for marketplace, collection, inventory and payment actions. Private addresses, passwords, audio and transcripts are excluded.</p></header>
    <section className="rounded-xl border border-slate-200 bg-white p-5">{query.isLoading?<p className="text-sm text-slate-500">Loading audit records…</p>:query.isError?<p role="alert" className="text-sm text-rose-700">Audit records could not be loaded. Administrator access is required.</p>:!query.data?.length?<p className="rounded-lg border border-dashed p-8 text-center text-sm text-slate-500">No audited actions have been recorded yet.</p>:<div className="space-y-2">{query.data.map(row=><article key={row.id} className="rounded-lg border border-slate-100 p-4"><div className="flex flex-wrap items-start justify-between gap-2"><div><p className="text-sm font-semibold text-ink">{row.action.replaceAll("_"," ")}</p><p className="mt-1 text-xs text-slate-500">{row.entity_type} · {row.entity_id} · actor {row.actor_id.slice(0,8)}</p></div><time className="text-xs text-slate-500">{new Date(row.created_at).toLocaleString()}</time></div><dl className="mt-3 flex flex-wrap gap-x-5 gap-y-1">{Object.entries(row.details).map(([key,value])=><div key={key} className="flex gap-1 text-xs"><dt className="text-slate-500">{key.replaceAll("_"," ")}:</dt><dd className="font-medium text-slate-700">{String(value)}</dd></div>)}</dl></article>)}</div>}</section>
  </div>;
}
