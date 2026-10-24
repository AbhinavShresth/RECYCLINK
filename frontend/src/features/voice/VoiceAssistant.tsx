import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ConversationProvider, useConversation } from "@elevenlabs/react";
import { useNavigate } from "react-router-dom";
import { Mic, MicOff, PhoneOff, ShieldCheck, Volume2 } from "lucide-react";
import { apiRequest } from "../../lib/api";

type Message = { message: string; role: string };
type Session = { signed_url: string; user_id: string; expires_in_minutes: number };
type ListingArgs = { category_code: string; quantity_grams: number; pickup_address: string; latitude: number; longitude: number; description?: string };

function VoiceSession({ activeRole }: { activeRole: string }) {
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([]);
  const [typed, setTyped] = useState("");
  const [notice, setNotice] = useState("");
  const provider = useQuery({ queryKey: ["voice-status"], queryFn: () => apiRequest<{configured:boolean;message:string}>("/api/v1/voice/status") });
  const conversation = useConversation({
    onMessage: ({ message, role }) => setMessages(current => [...current.slice(-19), { message, role }]),
    onError: (message) => setNotice(`Voice session error: ${message}`),
    onDisconnect: () => setNotice("Voice session ended."),
    clientTools: {
      open_waste_uploader: () => { navigate("/identify"); return "Waste image upload page opened. Classification is performed by the RecycLink backend after an image is uploaded."; },
      find_nearby_recyclers: async (args: { category_code: string; latitude: number; longitude: number; quantity_grams: number }) => {
        const result = await apiRequest<Array<{business_name:string;straight_line_distance_meters:number;indicative_price_minor_per_kg:number|null;verified:boolean;distance_metric:string}>>(`/api/v1/recyclers/discover?category=${encodeURIComponent(args.category_code)}&latitude=${args.latitude}&longitude=${args.longitude}&quantity_grams=${args.quantity_grams}`);
        return JSON.stringify(result.slice(0, 8));
      },
      get_collection_history: async () => {
        const rows = await apiRequest<Array<{id:string;status:string;estimated_quantity_grams:number;actual_quantity_grams:number|null;scheduled_at:string|null;created_at:string;listing:{category_code:string}}>>("/api/v1/collections");
        return JSON.stringify(rows.slice(0, 20).map(row => ({id:row.id,status:row.status,material:row.listing.category_code,estimated_grams:row.estimated_quantity_grams,actual_grams:row.actual_quantity_grams,scheduled_at:row.scheduled_at,created_at:row.created_at})));
      },
      get_collection_status: async (args: { collection_id: string }) => {
        const row = await apiRequest<{id:string;status:string;estimated_quantity_grams:number;actual_quantity_grams:number|null;scheduled_at:string|null;listing:{category_code:string}}>(`/api/v1/collections/${encodeURIComponent(args.collection_id)}`);
        return JSON.stringify({id:row.id,status:row.status,material:row.listing.category_code,estimated_grams:row.estimated_quantity_grams,actual_grams:row.actual_quantity_grams,scheduled_at:row.scheduled_at});
      },
      get_account_analytics: async () => {
        const endpoint = activeRole === "ADMIN" ? "admin" : activeRole === "RECYCLER" ? "recycler" : "user";
        const result = await apiRequest<Record<string, unknown>>(`/api/v1/analytics/${endpoint}`);
        return JSON.stringify(result);
      },
      create_collection_listing: async (args: ListingArgs) => {
        if (!Number.isSafeInteger(args.quantity_grams) || args.quantity_grams <= 0 || !Number.isFinite(args.latitude) || !Number.isFinite(args.longitude)) return "Request rejected: quantity must be positive whole grams and coordinates must be valid numbers.";
        const approved = window.confirm(`Publish this waste listing?\n\n${args.category_code}, ${args.quantity_grams.toLocaleString()} grams\nPickup: ${args.pickup_address}\n\nThe address will be shared only with the recycler after you accept an offer.`);
        if (!approved) return "The user did not confirm. No listing was created.";
        const listing = await apiRequest<{id:string;status:string;category_code:string;quantity_grams:number}>("/api/v1/listings", { method:"POST", body:JSON.stringify({category_code:args.category_code,quantity_grams:args.quantity_grams,pickup_address:args.pickup_address,location:{latitude:args.latitude,longitude:args.longitude},description:args.description}) });
        navigate("/marketplace");
        return JSON.stringify({created:true,id:listing.id,status:listing.status,category_code:listing.category_code,quantity_grams:listing.quantity_grams,note:"This creates an open marketplace listing. A collection request exists only after a recycler offer is accepted."});
      },
    },
  });

  async function start(textOnly = false) {
    if (!provider.data?.configured) { setNotice(provider.data?.message ?? "Voice configuration is not available. Use the visual workflows below."); return; }
    setNotice("Requesting a short-lived secure voice session…");
    try {
      if (!textOnly) {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach(track => track.stop());
      }
      const session = await apiRequest<Session>("/api/v1/voice/session", { method:"POST" });
      await conversation.startSession({ signedUrl: session.signed_url, textOnly });
      setNotice(textOnly ? "Text conversation connected. Your agent must have text-only mode enabled." : "Connected. Hindi or English can be used according to your agent configuration.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not start a voice session. Use typed actions below.");
    }
  }

  return <div className="space-y-5">
    <header><p className="text-xs font-bold uppercase tracking-widest text-leaf">Conversational AI</p><h2 className="mt-1 text-2xl font-semibold">Voice assistant</h2><p className="mt-1 max-w-2xl text-sm leading-6 text-slate-600">Use the configured ElevenLabs agent to search your records and navigate workflows. The backend authorizes every data request. Consequential listing creation requires an explicit browser confirmation.</p></header>
    <section className="grid gap-4 lg:grid-cols-[1fr_.8fr]">
      <article className="rounded-xl border border-slate-200 bg-white p-6"><div className="flex items-center gap-3"><span className={`grid h-11 w-11 place-items-center rounded-full ${conversation.status === "connected" ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-500"}`}><Mic size={20}/></span><div><h3 className="font-semibold">{conversation.status === "connected" ? conversation.isListening ? "Listening" : conversation.isSpeaking ? "Assistant speaking" : "Connected" : conversation.status === "connecting" ? "Connecting" : "Not connected"}</h3><p className="text-xs text-slate-500">{conversation.status === "connected" ? "Microphone session active" : "ElevenLabs credentials and an agent are required"}</p></div></div>
        <div className="mt-5 flex flex-wrap gap-2">{conversation.status === "connected" ? <><button onClick={()=>conversation.setMuted(!conversation.isMuted)} className="inline-flex items-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-semibold">{conversation.isMuted?<Mic size={16}/>:<MicOff size={16}/>} {conversation.isMuted?"Unmute":"Mute"}</button><button onClick={()=>conversation.endSession()} className="inline-flex items-center gap-2 rounded-lg bg-rose-700 px-4 py-2.5 text-sm font-semibold text-white"><PhoneOff size={16}/>End session</button></> : <><button onClick={()=>void start()} disabled={conversation.status==="connecting"||provider.isLoading||provider.data?.configured===false} className="inline-flex items-center gap-2 rounded-lg bg-forest px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"><Mic size={16}/>{provider.isLoading?"Checking provider…":provider.data?.configured?"Start voice session":"Voice not configured"}</button>{provider.data?.configured&&<button onClick={()=>void start(true)} disabled={conversation.status==="connecting"} className="rounded-lg border px-4 py-2.5 text-sm font-semibold text-slate-700 disabled:opacity-50">Start text conversation</button>}</>}</div>
        {provider.data&&!provider.data.configured&&<p className="mt-3 text-sm text-slate-600">{provider.data.message}</p>}
        {notice&&<p role="status" className="mt-4 rounded-lg bg-slate-50 p-3 text-sm text-slate-700">{notice}</p>}
        <div className="mt-5 max-h-72 space-y-2 overflow-auto rounded-lg border border-slate-100 p-3" aria-live="polite">{messages.length?messages.map((item,index)=><p key={`${index}-${item.role}`} className={`rounded-lg p-3 text-sm ${item.role==="user"?"ml-6 bg-emerald-50":"mr-6 bg-slate-50"}`}><span className="mb-1 block text-[10px] font-bold uppercase text-slate-500">{item.role}</span>{item.message}</p>):<p className="py-8 text-center text-sm text-slate-400">Your session transcript appears here while this page is open. It is not saved by RecycLink.</p>}</div>
        {conversation.status === "connected"&&<form className="mt-3 flex gap-2" onSubmit={event=>{event.preventDefault();if(typed.trim()){conversation.sendUserMessage(typed.trim());setTyped("");}}}><label className="sr-only" htmlFor="voice-text">Type a message to the connected assistant</label><input id="voice-text" value={typed} onChange={e=>setTyped(e.target.value)} placeholder="Type to the assistant…" className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"/><button className="rounded-lg border px-3 py-2 text-sm font-semibold">Send</button></form>}
      </article>
      <article className="rounded-xl border border-slate-200 bg-white p-6"><div className="flex items-center gap-2"><ShieldCheck size={18} className="text-leaf"/><h3 className="font-semibold">Available actions</h3></div><p className="mt-2 text-sm text-slate-500">Agent tools must be configured with the names below in the ElevenLabs dashboard and enabled as client tools.</p><ul className="mt-4 space-y-3 text-sm">{["open_waste_uploader · opens the image classification page","find_nearby_recyclers · queries compatible businesses and service areas","get_collection_history · reads your own collection records","get_collection_status · reads one collection you can access","get_account_analytics · reads analytics allowed for your current role","create_collection_listing · asks for browser confirmation before publishing"].map(line=><li key={line} className="rounded-lg bg-slate-50 p-3">{line}</li>)}</ul><div className="mt-4 flex flex-wrap gap-2"><button onClick={()=>navigate("/identify")} className="rounded-lg border px-3 py-2 text-xs font-semibold">Identify waste</button><button onClick={()=>navigate("/marketplace")} className="rounded-lg border px-3 py-2 text-xs font-semibold">Browse marketplace</button><button onClick={()=>navigate("/collections")} className="rounded-lg border px-3 py-2 text-xs font-semibold">My collections</button></div><div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-950"><Volume2 size={14} className="mr-1 inline"/>Audio is sent to ElevenLabs when the session is active. RecycLink does not store raw recordings. Hindi support depends on the selected agent/model configuration.</div></article>
    </section>
  </div>;
}

export default function VoiceAssistant({ activeRole }: { activeRole: string }) {
  return <ConversationProvider><VoiceSession activeRole={activeRole}/></ConversationProvider>;
}
