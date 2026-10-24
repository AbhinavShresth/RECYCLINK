import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Camera, CheckCircle2, LoaderCircle, Upload } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { apiRequest } from "../../lib/api";

type Prediction = { prediction_id: string; predicted_class: string; candidate_class: string; confidence: number; top_predictions: { class: string; confidence: number }[]; needs_confirmation: boolean; model_version: string; confidence_note: string };
const categories = ["plastic", "paper", "metal", "glass", "organic", "textile", "electronics", "other"];

async function getStatus() { return apiRequest<{ ready: boolean; status: string; model_version?: string; message?: string }>("/api/v1/ai/status"); }
async function getHistory() { return apiRequest<Array<{ prediction_id: string; predicted_class: string; confidence: number; model_version: string; created_at: string }>>("/api/v1/ai/history"); }

export default function IdentifyWaste({ onCreateListing }: { onCreateListing?: () => void } = {}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const status = useQuery({ queryKey: ["model-status"], queryFn: getStatus });
  const history = useQuery({ queryKey: ["classification-history"], queryFn: getHistory, retry: false });
  const [file, setFile] = useState<File | null>(null);
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [manualCategory, setManualCategory] = useState("plastic");
  const [error, setError] = useState("");
  const classify = useMutation({ mutationFn: async (selected: File) => {
    const form = new FormData(); form.append("file", selected);
    const csrf = document.cookie.split("; ").find((part) => part.startsWith("csrf_token="))?.split("=").slice(1).join("=");
    const response = await fetch("/api/v1/ai/classify", { method: "POST", body: form, credentials: "include", headers: csrf ? { "X-CSRF-Token": decodeURIComponent(csrf) } : {} });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail ?? "Classification request failed");
    return data as Prediction;
  }, onSuccess: async (data) => { setPrediction(data); setManualCategory(data.candidate_class); setError(""); await queryClient.invalidateQueries({ queryKey: ["classification-history"] }); }, onError: (e) => { setPrediction(null); setError(e instanceof Error ? e.message : "Classification failed"); } });
  const feedback = useMutation({ mutationFn: async () => apiRequest("/api/v1/ai/feedback", { method: "POST", body: JSON.stringify({ prediction_id: prediction?.prediction_id, confirmed_class: manualCategory }) }), onSuccess: async () => { setError(""); await queryClient.invalidateQueries({ queryKey: ["classification-history"] }); }, onError: (e) => setError(e instanceof Error ? e.message : "Could not save confirmation") });
  const selectFile = (next?: File) => { if (!next) return; setError(""); setPrediction(null); if (!next.type.match(/^image\/(jpeg|png|webp)$/)) { setFile(null); setError("Choose a JPEG, PNG, or WebP image."); return; } if (next.size > 8 * 1024 * 1024) { setFile(null); setError("Image must be 8 MB or smaller."); return; } setFile(next); };
  const continueToListing = () => {
    onCreateListing?.();
    navigate("/marketplace", { state: { imageListingDraft: { category_code: manualCategory, classification_id: prediction?.prediction_id, image_name: file?.name } } });
  };

  return <div className="mx-auto max-w-4xl space-y-6">
    <header><p className="text-xs font-bold uppercase tracking-widest text-leaf">Material guidance</p><h2 className="mt-2 text-2xl font-semibold text-ink">Identify waste</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">A photo can suggest a broad material category. It cannot verify polymer type, contamination, hazardous properties, or local recyclability. Please review the result.</p></header>
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <div className={`mb-5 rounded-lg border p-4 text-sm ${status.data?.ready ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "border-amber-200 bg-amber-50 text-amber-950"}`} role="status">
        {status.data?.ready ? <><CheckCircle2 size={17} className="mr-2 inline"/>Model ready · {status.data.model_version}</> : <><AlertTriangle size={17} className="mr-2 inline"/>{status.data?.message ?? (status.isLoading ? "Checking model availability…" : "Model status unavailable. Upload is disabled until a trained checkpoint is installed.")}</>}
      </div>
      <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" capture="environment" className="sr-only" onChange={(e) => selectFile(e.target.files?.[0])} aria-label="Choose waste photo" />
      <button type="button" onClick={() => fileRef.current?.click()} className="flex min-h-48 w-full flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 px-6 text-center hover:border-forest hover:bg-emerald-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-forest">
        {file ? <><Camera size={24} className="text-leaf"/><span className="mt-3 font-semibold text-ink">{file.name}</span><span className="mt-1 text-xs text-slate-500">Choose another image</span></> : <><Upload size={24} className="text-leaf"/><span className="mt-3 font-semibold text-ink">Select or capture a waste photo</span><span className="mt-1 text-xs text-slate-500">JPEG, PNG or WebP · max 8 MB · stored as image hash only</span></>}
      </button>
      <div className="mt-5 flex flex-wrap items-end gap-3"><button type="button" disabled={!file || !status.data?.ready || classify.isPending} onClick={() => file && classify.mutate(file)} className="inline-flex items-center gap-2 rounded-lg bg-forest px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40">{classify.isPending && <LoaderCircle size={16} className="animate-spin"/>}Classify image</button><span className="text-xs text-slate-500">Manual selection is available if the model is not configured.</span></div>
      {error && <p role="alert" className="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
    </section>
    {!status.data?.ready && <section className="rounded-xl border border-slate-200 bg-white p-6"><h3 className="font-semibold text-ink">Choose a category manually</h3><p className="mt-1 text-sm text-slate-500">This selection is not an AI prediction. Training data and a trained model checkpoint are not currently installed.</p><label htmlFor="manual-category" className="mt-4 block text-sm font-medium">Material category</label><select id="manual-category" value={manualCategory} onChange={(e) => setManualCategory(e.target.value)} className="mt-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">{categories.map((c) => <option key={c} value={c}>{c[0].toUpperCase()+c.slice(1)}</option>)}</select>{file && <button type="button" onClick={continueToListing} className="ml-3 rounded-lg bg-forest px-4 py-2.5 text-sm font-semibold text-white">Create listing from this photo</button>}</section>}
    {prediction && <section className="rounded-xl border border-slate-200 bg-white p-6"><p className="text-xs font-bold uppercase tracking-widest text-leaf">Model suggestion · {prediction.model_version}</p><h3 className="mt-2 text-xl font-semibold text-ink">{prediction.needs_confirmation ? "Uncertain result" : prediction.candidate_class[0].toUpperCase()+prediction.candidate_class.slice(1)}</h3><p className="mt-1 text-sm text-slate-600">Score {Math.round(prediction.confidence*100)}% · {prediction.confidence_note}</p><div className="mt-4 space-y-2">{prediction.top_predictions.map((item) => <div key={item.class} className="flex items-center gap-3 text-sm"><span className="w-24 capitalize text-slate-600">{item.class}</span><div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-leaf" style={{ width: `${Math.round(item.confidence*100)}%` }}/></div><span className="w-10 text-right text-xs text-slate-500">{Math.round(item.confidence*100)}%</span></div>)}</div><div className="mt-5 flex flex-wrap items-end gap-3"><label className="text-sm">Confirm or correct<select value={manualCategory} onChange={(e)=>setManualCategory(e.target.value)} className="mt-1 block rounded-lg border border-slate-300 bg-white px-3 py-2">{categories.map(c=><option key={c} value={c}>{c}</option>)}</select></label><button onClick={()=>feedback.mutate()} disabled={feedback.isPending} className="rounded-lg bg-forest px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">Save reviewed feedback</button>{file && <button type="button" onClick={continueToListing} className="rounded-lg border border-forest px-4 py-2.5 text-sm font-semibold text-forest">Create listing</button>}</div></section>}
    <section className="rounded-xl border border-slate-200 bg-white p-6"><h3 className="font-semibold text-ink">Classification history</h3><p className="mt-1 text-sm text-slate-500">Saved predictions for this signed-in account only.</p>{history.isError ? <p className="mt-4 text-sm text-slate-500">Sign in to view history.</p> : !history.data?.length ? <p className="mt-4 rounded-lg bg-slate-50 p-4 text-sm text-slate-500">No model classifications recorded yet.</p> : <ul className="mt-4 divide-y divide-slate-100">{history.data.map(row=><li key={row.prediction_id} className="flex justify-between gap-3 py-3 text-sm"><span className="capitalize">{row.predicted_class}</span><span className="text-slate-500">{row.model_version} · {new Date(row.created_at).toLocaleDateString()}</span></li>)}</ul>}</section>
  </div>;
}
