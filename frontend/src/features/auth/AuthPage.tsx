import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { Leaf, LoaderCircle, Recycle } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { login, register } from "../../lib/api";

const loginSchema = z.object({ email: z.string().email("Enter a valid email"), password: z.string().min(1, "Enter your password") });
const registerSchema = z.object({
  full_name: z.string().trim().min(2, "Enter your name").max(120),
  email: z.string().email("Enter a valid email"),
  password: z.string().min(12, "Use at least 12 characters").max(128),
  preferred_language: z.enum(["en", "hi"]),
  enable_recycler: z.boolean(),
});

type LoginValues = z.infer<typeof loginSchema>;
type RegisterValues = z.infer<typeof registerSchema>;

function FieldError({ message }: { message?: string }) {
  return message ? <p role="alert" className="mt-1 text-xs text-red-700">{message}</p> : null;
}

export default function AuthPage({ onAuthenticated }: { onAuthenticated: () => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const loginForm = useForm<LoginValues>({ resolver: zodResolver(loginSchema), defaultValues: { email: "", password: "" } });
  const registerForm = useForm<RegisterValues>({ resolver: zodResolver(registerSchema), defaultValues: { full_name: "", email: "", password: "", preferred_language: "en", enable_recycler: false } });

  async function submitLogin(values: LoginValues) {
    setBusy(true); setError("");
    try { await login(values); onAuthenticated(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to sign in"); }
    finally { setBusy(false); }
  }

  async function submitRegistration(values: RegisterValues) {
    setBusy(true); setError("");
    try { await register(values); onAuthenticated(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to create account"); }
    finally { setBusy(false); }
  }

  const inputClass = "mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-ink outline-none focus:border-forest focus:ring-2 focus:ring-emerald-100";
  return (
    <main className="grid min-h-screen bg-canvas lg:grid-cols-[1.1fr_.9fr]">
      <section className="hidden flex-col justify-between bg-forest p-10 text-white lg:flex xl:p-16">
        <div className="flex items-center gap-3"><span className="grid h-11 w-11 place-items-center rounded-xl bg-white/10 text-lime-200"><Recycle size={24}/></span><span className="text-xl font-bold">RecycLink</span></div>
        <div className="max-w-lg"><p className="text-xs font-bold uppercase tracking-[.2em] text-lime-200">Waste has another use</p><h1 className="mt-5 text-4xl font-semibold leading-tight tracking-tight xl:text-5xl">Make the next step in your material’s journey easier.</h1><p className="mt-5 max-w-md leading-7 text-emerald-50/80">Connect households, businesses, and recovery partners through accountable local collection.</p></div>
        <p className="text-xs text-emerald-50/60">A circularity platform · RecycLink</p>
      </section>
      <section className="flex items-center justify-center px-5 py-10 sm:px-10">
        <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
          <div className="mb-6 flex items-center gap-2 text-forest lg:hidden"><Leaf/><span className="font-bold">RecycLink</span></div>
          <h2 className="text-2xl font-semibold tracking-tight text-ink">{mode === "login" ? "Welcome back" : "Create your account"}</h2>
          <p className="mt-2 text-sm text-slate-500">{mode === "login" ? "Sign in to manage your recycling activity." : "Your account can also enable recycler tools."}</p>
          <div className="mt-5 grid grid-cols-2 rounded-lg bg-slate-100 p-1" role="tablist" aria-label="Account access">
            <button type="button" role="tab" aria-selected={mode === "login"} onClick={() => { setError(""); setMode("login"); }} className={`rounded-md py-2 text-sm font-medium ${mode === "login" ? "bg-white text-forest shadow-sm" : "text-slate-500"}`}>Sign in</button>
            <button type="button" role="tab" aria-selected={mode === "register"} onClick={() => { setError(""); setMode("register"); }} className={`rounded-md py-2 text-sm font-medium ${mode === "register" ? "bg-white text-forest shadow-sm" : "text-slate-500"}`}>Register</button>
          </div>
          {mode === "login" ? (
            <form className="mt-5 space-y-4" onSubmit={loginForm.handleSubmit(submitLogin)}>
              <label className="block text-sm font-medium text-slate-700">Email<input autoComplete="email" className={inputClass} type="email" {...loginForm.register("email")}/><FieldError message={loginForm.formState.errors.email?.message}/></label>
              <label className="block text-sm font-medium text-slate-700">Password<input autoComplete="current-password" className={inputClass} type="password" {...loginForm.register("password")}/><FieldError message={loginForm.formState.errors.password?.message}/></label>
              {error && <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">{error}</p>}
              <button disabled={busy} className="flex w-full items-center justify-center gap-2 rounded-lg bg-forest px-4 py-3 text-sm font-semibold text-white hover:bg-leaf disabled:opacity-60">{busy && <LoaderCircle className="animate-spin" size={16}/>}Sign in</button>
            </form>
          ) : (
            <form className="mt-5 space-y-4" onSubmit={registerForm.handleSubmit(submitRegistration)}>
              <label className="block text-sm font-medium text-slate-700">Full name<input autoComplete="name" className={inputClass} {...registerForm.register("full_name")}/><FieldError message={registerForm.formState.errors.full_name?.message}/></label>
              <label className="block text-sm font-medium text-slate-700">Email<input autoComplete="email" className={inputClass} type="email" {...registerForm.register("email")}/><FieldError message={registerForm.formState.errors.email?.message}/></label>
              <label className="block text-sm font-medium text-slate-700">Password<input autoComplete="new-password" className={inputClass} type="password" {...registerForm.register("password")}/><FieldError message={registerForm.formState.errors.password?.message}/></label>
              <label className="block text-sm font-medium text-slate-700">Preferred language<select className={inputClass} {...registerForm.register("preferred_language")}><option value="en">English</option><option value="hi">हिन्दी</option></select></label>
              <label className="flex items-start gap-2 rounded-lg bg-canvas p-3 text-sm text-slate-700"><input type="checkbox" className="mt-0.5 accent-forest" {...registerForm.register("enable_recycler")}/><span><b>Enable recycler capabilities</b><span className="mt-0.5 block text-xs text-slate-500">You can also create listings as a household.</span></span></label>
              {error && <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">{error}</p>}
              <button disabled={busy} className="flex w-full items-center justify-center gap-2 rounded-lg bg-forest px-4 py-3 text-sm font-semibold text-white hover:bg-leaf disabled:opacity-60">{busy && <LoaderCircle className="animate-spin" size={16}/>}Create account</button>
            </form>
          )}
          <p className="mt-5 text-xs leading-5 text-slate-500">Your session is held in an HttpOnly cookie. RecycLink does not store session tokens in browser local storage.</p>
        </div>
      </section>
    </main>
  );
}
