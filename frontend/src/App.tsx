import { lazy, Suspense, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, ArrowRight, BarChart3, Boxes, Camera, ChevronDown, Clock3, CreditCard, Leaf, MapPin, MessageCircle, Recycle, Route, ShieldAlert, ShieldCheck, Truck, Users, Waves } from "lucide-react";
import { NavLink, Route as RouterRoute, Routes } from "react-router-dom";
import { apiRequest, getApiStatus, getMe, logout, type User } from "./lib/api";
import AuthPage from "./features/auth/AuthPage";
import IdentifyWaste from "./features/classification/IdentifyWaste";
import Marketplace from "./features/marketplace/Marketplace";
import Collections from "./features/collections/Collections";
import Inventory from "./features/inventory/Inventory";
import Transactions from "./features/transactions/Transactions";
const RoutePlanner = lazy(() => import("./features/routes/RoutePlanner"));
const BinMonitor = lazy(() => import("./features/bins/BinMonitor"));
const Analytics = lazy(() => import("./features/analytics/Analytics"));
const VoiceAssistant = lazy(() => import("./features/voice/VoiceAssistant"));
const AdminAudit = lazy(() => import("./features/admin/AdminAudit"));

const navigation = [
  { to: "/", label: "Overview", icon: Activity },
  { to: "/identify", label: "Identify waste", icon: Camera },
  { to: "/marketplace", label: "Marketplace", icon: Recycle },
  { to: "/collections", label: "Collections", icon: Truck },
  { to: "/routes", label: "Map & routes", icon: Route },
  { to: "/bins", label: "Smart bins", icon: Waves },
  { to: "/inventory", label: "Inventory & recovery", icon: Boxes },
  { to: "/transactions", label: "Transactions", icon: CreditCard },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/voice", label: "Voice assistant", icon: MessageCircle },
  { to: "/admin", label: "Administration", icon: ShieldCheck },
];

function ApiStatus() {
  const status = useQuery({ queryKey: ["api-health"], queryFn: getApiStatus });
  return (
    <div className="flex items-center gap-2 text-xs text-slate-500" role="status" aria-live="polite">
      <span className={`h-2 w-2 rounded-full ${status.isSuccess ? "bg-emerald-500" : status.isError ? "bg-amber-500" : "bg-slate-300"}`} />
      {status.isSuccess ? "API and database ready" : status.isError ? "API unavailable" : "Checking services…"}
    </div>
  );
}

function Overview({ role }: { role: string }) {
  const endpoint = role === "ADMIN" ? "admin" : role === "RECYCLER" ? "recycler" : "user";
  const analytics = useQuery({ queryKey: ["overview-metrics", endpoint], queryFn: () => apiRequest<Record<string, unknown>>(`/api/v1/analytics/${endpoint}`) });
  const collections = useQuery({ queryKey: ["overview-collections", role], queryFn: () => apiRequest<Array<{id:string;status:string;scheduled_at:string|null;estimated_quantity_grams:number;listing:{category_code:string}}>>("/api/v1/collections") });
  const value = (key: string) => typeof analytics.data?.[key] === "number" ? Number(analytics.data[key]).toLocaleString() : "—";
  const metrics = role === "ADMIN" ? [["Active accounts",value("active_users"),"Live account records"],["Active recyclers",value("active_recyclers"),"Accounts with recycler capability"],["Open listings",value("open_listings"),"Marketplace requests still open"],["Recovered output",value("recorded_recovered_quantity_grams"),"grams recorded from processing"]] : role === "RECYCLER" ? [["Requests received",value("collections_received"),"Your assigned collection requests"],["Completed",value("completed_collections"),"Completed collection records"],["Collected mass",value("actual_collected_quantity_grams"),"grams weighed at collection"],["Recorded sales",`₹${(Number(analytics.data?.sales_value_minor_inr||0)/100).toFixed(2)}`,"Recorded transaction value"]] : [["Waste submitted",value("submitted_quantity_grams"),"grams estimated in your listings"],["Collected",value("collected_quantity_grams"),"grams confirmed on completed collections"],["Completed collections",value("completed_collections"),"Your completed records"],["Awaiting action",value("pending_collections"),"Accepted and active collection requests"]];
  return (
    <div className="space-y-6">
      <section className="rounded-2xl bg-forest p-8 text-white shadow-sm sm:p-10">
        <div className="max-w-2xl">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-lime-200">{role === "ADMIN" ? "Platform operations" : role === "RECYCLER" ? "Recovery workspace" : "Circularity, connected"}</p>
          <h2 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">{role === "ADMIN" ? "Monitor material recovery across the platform." : role === "RECYCLER" ? "Turn incoming materials into measurable recovery." : "Give useful materials their next destination."}</h2>
          <p className="mt-4 max-w-xl leading-7 text-emerald-50/80">{role === "ADMIN" ? "Platform totals distinguish reported, collected, processed, and recovered quantities." : "Identify materials, meet suitable recovery partners, and follow each collection through its next step."}</p>
          <NavLink to={role === "ADMIN" ? "/analytics" : role === "RECYCLER" ? "/marketplace" : "/identify"} className="mt-6 inline-flex items-center gap-2 rounded-lg bg-white px-4 py-3 font-semibold text-forest hover:bg-lime-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white">{role === "ADMIN" ? "Open analytics" : role === "RECYCLER" ? "Review requests" : "Start with a photo"} <ArrowRight size={16} /></NavLink>
        </div>
      </section>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map(([label,metric,note],index)=><Metric key={label} icon={[Recycle,Truck,Leaf,Clock3][index]} label={label} value={analytics.isLoading?"…":metric} note={analytics.isError?"Analytics unavailable":note}/>) }
      </div>
      <div className="grid gap-4 lg:grid-cols-[1.2fr_.8fr]">
        <section className="rounded-xl border border-slate-200 bg-white p-6">
          <div className="flex items-start justify-between gap-3"><div><h3 className="font-semibold text-ink">{role === "ADMIN" ? "Platform collections" : "Recent collections"}</h3><p className="mt-1 text-sm text-slate-500">Authorized collection records from the API.</p></div><ApiStatus /></div>
          {collections.isLoading?<p className="mt-6 text-sm text-slate-500">Loading recent activity…</p>:collections.isError?<p role="alert" className="mt-6 text-sm text-rose-700">Collection activity is unavailable.</p>:!collections.data?.length?<div className="mt-6 rounded-lg border border-dashed border-slate-200 px-5 py-10 text-center"><p className="text-sm font-medium text-slate-700">No collections in your account yet</p><p className="mt-1 text-sm text-slate-500">Create a listing or browse suitable requests to get started.</p></div>:<div className="mt-4 space-y-2">{collections.data.slice(0,5).map(row=><div key={row.id} className="flex items-center justify-between gap-3 rounded-lg bg-canvas p-3"><div><p className="text-sm font-semibold capitalize">{row.listing.category_code} · {(row.estimated_quantity_grams/1000).toFixed(2)} kg</p><p className="mt-1 text-xs text-slate-500">{row.scheduled_at?new Date(row.scheduled_at).toLocaleString():"Pickup not scheduled"}</p></div><span className="rounded-full bg-white px-2 py-1 text-[10px] font-bold text-forest">{row.status.replaceAll("_"," ")}</span></div>)}</div>}
        </section>
        <section className="rounded-xl border border-slate-200 bg-white p-6"><h3 className="font-semibold text-ink">Next steps</h3><div className="mt-4 space-y-3"><Action to="/identify" icon={Camera} title="Identify a material" copy="Upload a photo for classification."/><Action to="/marketplace" icon={Users} title="Find a recovery partner" copy="Explore suitable local recyclers."/><Action to="/collections" icon={MapPin} title="Track a collection" copy="See pickup status and history."/></div></section>
      </div>
      {analytics.isError&&<div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950"><ShieldAlert className="mr-2 inline" size={17}/>Your dashboard metrics could not be refreshed. Other connected workflows remain available.</div>}
    </div>
  );
}

function Metric({ icon: Icon, label, value, note }: { icon: typeof Activity; label: string; value: string; note: string }) {
  return <section className="rounded-xl border border-slate-200 bg-white p-5"><div className="flex items-center justify-between"><p className="text-sm text-slate-500">{label}</p><Icon size={18} className="text-leaf"/></div><p className="mt-4 text-2xl font-semibold text-ink">{value}</p><p className="mt-1 text-xs text-slate-500">{note}</p></section>;
}

function Action({ to, icon: Icon, title, copy }: { to: string; icon: typeof Activity; title: string; copy: string }) {
  return <NavLink to={to} className="flex items-center gap-3 rounded-lg p-3 hover:bg-canvas focus-visible:outline focus-visible:outline-2 focus-visible:outline-forest"><span className="rounded-lg bg-emerald-50 p-2 text-leaf"><Icon size={17}/></span><span className="min-w-0"><span className="block text-sm font-semibold text-ink">{title}</span><span className="mt-0.5 block text-xs text-slate-500">{copy}</span></span><ArrowRight size={15} className="ml-auto shrink-0 text-slate-400"/></NavLink>;
}

function ComingSoon({ title }: { title: string }) {
  return <section className="rounded-xl border border-slate-200 bg-white p-8"><p className="text-xs font-bold uppercase tracking-widest text-leaf">Workspace</p><h2 className="mt-2 text-2xl font-semibold text-ink">{title}</h2><p className="mt-3 max-w-xl text-sm leading-6 text-slate-600">This page will be enabled when its API, authorization, and tests are implemented. No demo results are shown as live data.</p></section>;
}

function Workspace({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [activeRole, setActiveRole] = useState(user.roles.includes("RECYCLER") ? "RECYCLER" : user.roles.includes("ADMIN") ? "ADMIN" : "USER");
  const visibleNavigation = navigation.filter(item => !(activeRole !== "RECYCLER" && ["/routes", "/inventory", "/transactions"].includes(item.to)) && !(activeRole !== "ADMIN" && item.to === "/admin"));
  return (
    <div className="min-h-screen bg-canvas text-ink">
      <aside className="fixed inset-y-0 left-0 z-10 hidden w-64 flex-col border-r border-slate-200 bg-white px-4 py-6 lg:flex">
        <NavLink to="/" className="mb-9 flex items-center gap-3 px-2"><span className="grid h-10 w-10 place-items-center rounded-xl bg-forest text-lime-200"><Recycle size={22}/></span><span><span className="block text-lg font-bold tracking-tight text-forest">RecycLink</span><span className="block text-[9px] font-semibold tracking-[.18em] text-slate-400">CIRCULARITY PLATFORM</span></span></NavLink>
        <p className="mb-2 px-3 text-[10px] font-bold tracking-[.15em] text-slate-400">WORKSPACE</p>
        <nav className="space-y-1" aria-label="Main navigation">{visibleNavigation.map(({ to, label, icon: Icon }) => <NavLink end={to === "/"} key={to} to={to} className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-forest ${isActive ? "bg-emerald-50 text-forest" : "text-slate-600 hover:bg-slate-50"}`}><Icon size={17}/>{label}</NavLink>)}</nav>
        <div className="mt-auto rounded-lg bg-canvas p-3 text-xs text-slate-500"><ApiStatus/></div>
      </aside>
      <main className="min-h-screen lg:pl-64">
        <header className="sticky top-0 z-[5] flex h-[72px] items-center justify-between border-b border-slate-200 bg-white/95 px-5 backdrop-blur sm:px-8">
          <div><p className="text-[10px] font-bold tracking-[.15em] text-slate-400">RECYCLINK / WORKSPACE</p><h1 className="mt-0.5 text-base font-semibold">Overview</h1></div>
          <div className="flex items-center gap-2">
            {(user.roles.includes("RECYCLER") || user.roles.includes("ADMIN")) && <label className="sr-only" htmlFor="role-switcher">Active role</label>}
            {(user.roles.includes("RECYCLER") || user.roles.includes("ADMIN")) && <select id="role-switcher" value={activeRole} onChange={(event) => setActiveRole(event.target.value)} className="rounded-lg border border-slate-200 bg-white px-2 py-2 text-xs font-medium text-slate-600"><option value="USER">Household</option>{user.roles.includes("RECYCLER") && <option value="RECYCLER">Recycler</option>}{user.roles.includes("ADMIN") && <option value="ADMIN">Admin</option>}</select>}
            <span className="hidden text-sm text-slate-600 sm:inline">{user.full_name}</span>
            <button onClick={onLogout} className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50">Sign out</button>
            <ChevronDown size={14} className="hidden text-slate-400 sm:block"/>
          </div>
        </header>
        <div className="mx-auto max-w-[1440px] p-4 sm:p-7"><Routes><RouterRoute path="/" element={<Overview role={activeRole}/>}/><RouterRoute path="/identify" element={<IdentifyWaste onCreateListing={() => setActiveRole("USER")}/>}/><RouterRoute path="/marketplace" element={<Marketplace activeRole={activeRole}/>}/><RouterRoute path="/collections" element={<Collections isRecycler={activeRole === "RECYCLER"}/>}/><RouterRoute path="/routes" element={<Suspense fallback={<div className="rounded-xl border bg-white p-8 text-sm text-slate-500">Loading route planner…</div>}><RoutePlanner/></Suspense>}/><RouterRoute path="/bins" element={<Suspense fallback={<div className="rounded-xl border bg-white p-8 text-sm text-slate-500">Loading bin monitor…</div>}><BinMonitor activeRole={activeRole}/></Suspense>}/><RouterRoute path="/inventory" element={<Inventory/>}/><RouterRoute path="/transactions" element={<Transactions/>}/><RouterRoute path="/analytics" element={<Suspense fallback={<div className="rounded-xl border bg-white p-8 text-sm text-slate-500">Loading analytics…</div>}><Analytics role={activeRole}/></Suspense>}/><RouterRoute path="/voice" element={<Suspense fallback={<div className="rounded-xl border bg-white p-8 text-sm text-slate-500">Loading voice tools…</div>}><VoiceAssistant activeRole={activeRole}/></Suspense>}/><RouterRoute path="/admin" element={<Suspense fallback={<div className="rounded-xl border bg-white p-8 text-sm text-slate-500">Loading administrator tools…</div>}><AdminAudit/></Suspense>}/><RouterRoute path="*" element={<ComingSoon title="Page not found"/>}/></Routes></div>
        <footer className="px-5 pb-6 text-center text-xs text-slate-400 sm:px-8">RecycLink · data-backed circularity workflows</footer>
      </main>
      <div className="fixed inset-x-0 bottom-0 z-20 flex border-t border-slate-200 bg-white lg:hidden" aria-label="Mobile navigation">{visibleNavigation.slice(0,5).map(({to,label,icon:Icon})=><NavLink key={to} end={to==="/"} to={to} aria-label={label} className={({isActive})=>`flex flex-1 flex-col items-center gap-1 py-2 text-[10px] ${isActive?"text-forest":"text-slate-500"}`}><Icon size={18}/>{label.split(" ")[0]}</NavLink>)}</div>
    </div>
  );
}

export default function App() {
  const me = useQuery({ queryKey: ["me"], queryFn: getMe, retry: false, staleTime: 30_000 });
  if (me.isLoading) return <div className="grid min-h-screen place-items-center text-sm text-slate-500">Loading secure session…</div>;
  if (me.isError) return <div className="grid min-h-screen place-items-center p-6"><div className="max-w-md rounded-xl border border-amber-200 bg-white p-6"><h1 className="font-semibold">RecycLink API unavailable</h1><p className="mt-2 text-sm text-slate-600">Start the backend and refresh. No local-only sign-in is being simulated.</p><button className="mt-4 rounded-lg bg-forest px-4 py-2 text-sm font-semibold text-white" onClick={() => void me.refetch()}>Retry connection</button></div></div>;
  if (!me.data) return <AuthPage onAuthenticated={() => { void me.refetch(); }} />;
  return <Workspace user={me.data} onLogout={() => { void logout().then(() => me.refetch()); }} />;
}
