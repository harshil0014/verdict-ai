import React, { useEffect, useRef, useState } from 'react';
import { ArrowRight, Check, FileText, GitBranch, KeyRound, LoaderCircle, LockKeyhole, ScanLine, ShieldCheck } from 'lucide-react';
import './saas.css';
import './account-controls.css';

export function AccountEntry({ api, onAuthenticated }: { api: (path: string, method?: string, body?: any) => Promise<any>; onAuthenticated: () => Promise<void> }) {
  const [mode, setMode] = useState('home');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [recovery, setRecovery] = useState('');
  const [saved, setSaved] = useState(false);
  const dialogRef = useRef<HTMLElement>(null);
  useEffect(() => {
    if (mode === 'home' && !recovery) return;
    const previous = document.activeElement as HTMLElement | null;
    const controls = () => Array.from(dialogRef.current?.querySelectorAll<HTMLElement>('input:not([disabled]), button:not([disabled]), a[href]') || []).filter(e => e.offsetParent !== null);
    controls()[0]?.focus();
    const key = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !recovery && !busy) { event.preventDefault(); setMode('home'); }
      if (event.key !== 'Tab') return;
      const items = controls(), first = items[0], last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    document.addEventListener('keydown', key);
    return () => { document.removeEventListener('keydown', key); previous?.focus(); };
  }, [mode, recovery, busy]);
  function open(next: string) { setError(''); setMode(next); }
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault(); setError(''); setBusy(true);
    const values = Object.fromEntries(new FormData(e.currentTarget));
    if (mode !== 'login' && values.password !== values.confirm) { setError('The passwords do not match.'); setBusy(false); return; }
    delete values.confirm;
    try {
      const result = await api('/auth/' + (mode === 'signup' ? 'register' : mode), 'POST', values);
      if (result.recovery_code) { setRecovery(result.recovery_code); setSaved(false); }
      else await onAuthenticated();
    } catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  }
  return <div className="public-site">
    <header className="public-nav"><a href="/" className="public-brand"><b>V</b> VERDICT<span>THE MISSING WITNESS</span></a><nav><a href="#how">How it works</a><button onClick={() => open('login')}>Sign in</button><button className="primary" onClick={() => open('signup')}>Create account <ArrowRight size={15}/></button></nav></header>
    <main className="public-main">
      <section className="public-hero">
        <div className="hero-copy"><span className="eyebrow"><i className="live-dot"/> EVIDENCE BEFORE CERTAINTY</span><h1>Find the evidence<br/>that changes<br/><em>the picture.</em></h1><p>Bring competing accounts into focus. Keep original records, trace every claim to its source, and ask for the witness that could resolve the uncertainty.</p><div className="hero-actions"><button className="primary large" onClick={() => open('signup')}>Start your investigation <ArrowRight size={18}/></button><a href="#how">Explore the workflow ↗</a></div><p className="hero-fine"><LockKeyhole size={14}/> Your account. Your private workspace. Saved in the cloud.</p></div>
        <div className="workflow-art" aria-label="Illustration of the investigation workflow"><div className="workflow-heading"><span>THE INVESTIGATION METHOD</span><ScanLine size={19}/></div><div className="workflow-record"><FileText/><div><strong>Original evidence</strong><small>Preserve the record. Inspect the source.</small></div><Check size={17}/></div><div className="workflow-line"/><div className="workflow-record"><GitBranch/><div><strong>Competing explanations</strong><small>What supports each account?</small></div></div><div className="workflow-branches"><span>What is known</span><span>What is missing</span></div><div className="missing-piece"><ScanLine size={28}/><span>THE MISSING WITNESS</span><strong>What would distinguish<br/>the two stories?</strong></div><div className="workflow-caption">An illustrated method — your workspace starts empty.</div></div>
      </section>
      <section className="public-method" id="how"><div><span className="eyebrow">A CLEARER WAY TO INVESTIGATE</span><h2>From scattered records<br/>to a reviewable account.</h2></div><div className="method-grid">{[[FileText,'01','Bring your own evidence','Create a case. Add notes or upload TXT, JSON and text PDFs. Original files and their integrity hashes stay with the case.'],[GitBranch,'02','Follow the source graph','Gemini examines the competing accounts. Inspect quoted claims, supporting sources, uncertainty and alternative explanations.'],[ScanLine,'03','Ask for the missing witness','Review a suggested question or write your own. Share a scoped request link, collect the response and investigate again.']].map(([Icon, n, title, text]: any) => <article key={n}><span className="method-number">{n}</span><Icon size={23}/><h3>{title}</h3><p>{text}</p></article>)}</div></section>
      <section className="public-trust"><ShieldCheck size={28}/><div><h2>Private records. Human decisions.</h2><p>Separate accounts and database-enforced case ownership. Cloud-saved originals, witness responses and audit history. AI analysis runs only after your consent; it is assistance, not a verdict.</p></div><div className="beta-note"><strong>Free public beta</strong><span>50 cases · 20 MB · 10 investigations/day per account. Shared capacity limits apply. Free hosting can pause when idle.</span></div></section>
      <section className="public-boundary"><strong>Honest by design.</strong> Merchant connections are not enabled for public accounts. The separate operator integration uses PayPal sandbox test funds only. VERDICT does not verify delivery, predict win rates or submit financial actions for you.</section>
    </main><footer className="public-footer"><strong>VERDICT</strong><span>Evidence before certainty.</span><a href="https://github.com/harshil0014/verdict-ai" target="_blank" rel="noreferrer">Open source ↗</a></footer>
    {(mode !== 'home' || recovery) && <div className="account-overlay"><section ref={dialogRef} className="account-dialog" role="dialog" aria-modal="true" aria-labelledby="account-title">
      {!recovery && <button className="account-close" aria-label="Close" onClick={() => open('home')}>×</button>}
      <KeyRound size={28}/><span className="eyebrow">YOUR PRIVATE WORKSPACE</span><h2 id="account-title">{recovery ? 'Save your recovery key.' : mode === 'signup' ? 'A clearer picture starts here.' : mode === 'recover' ? 'Recover your account.' : 'Welcome back.'}</h2>
      {recovery ? <><p>This one-time key lets you reset your password. Store it in a password manager. We do not collect email addresses and cannot email you a reset link.</p><code className="recovery-key">{recovery}</code><button className="secondary" onClick={async () => { try { await navigator.clipboard.writeText(recovery); setSaved(true); } catch { setError('Copy the key manually and confirm below.'); } }}>{saved ? 'Copied' : 'Copy recovery key'}</button><label className="recovery-confirm"><input type="checkbox" checked={saved} onChange={e => setSaved(e.target.checked)}/> I have stored my recovery key safely.</label><button className="primary large" disabled={!saved || busy} onClick={async () => { setBusy(true); try { await onAuthenticated(); } catch (e: any) { setError(e.message); setBusy(false); } }}>Enter my workspace <ArrowRight size={17}/></button></> : <form onSubmit={submit}>
      <p>{mode === 'signup' ? 'Create a free account. Your workspace starts empty and belongs only to you.' : mode === 'recover' ? 'Use the recovery key saved when you registered. This signs out all previous sessions.' : 'Sign in to return to your cases and original records.'}</p>
      {mode === 'signup' && <label>Your name<input name="display_name" autoComplete="name" required minLength={1} maxLength={80}/></label>}
      <label>Username<input name="username" autoComplete="username" required pattern="[a-zA-Z0-9][a-zA-Z0-9_-]{2,31}" minLength={3} maxLength={32}/><small>3–32 letters, numbers, underscores or hyphens.</small></label>
      {mode === 'recover' && <label>Recovery key<input name="recovery_code" required autoComplete="off" minLength={20}/></label>}
      <label>{mode === 'recover' ? 'New password' : 'Password'}<input name="password" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required minLength={12} maxLength={128}/>{mode !== 'login' && <small>At least 12 characters. Use a unique password.</small>}</label>
      {mode !== 'login' && <label>Confirm password<input name="confirm" type="password" autoComplete="new-password" required minLength={12} maxLength={128}/></label>}
      {mode === 'signup' && <p className="fine">You will receive a one-time recovery key. Save it securely; there is no email-based password reset. Upload only records you are authorized to share.</p>}
      <button className="primary large" disabled={busy}>{busy ? <LoaderCircle className="spin" size={18}/> : <ArrowRight size={18}/>} {mode === 'signup' ? 'Create my account' : mode === 'recover' ? 'Reset password' : 'Sign in'}</button>
      <div className="account-switch">{mode === 'login' ? <><button type="button" onClick={() => open('signup')}>Create an account</button><button type="button" onClick={() => open('recover')}>Recover account</button></> : <button type="button" onClick={() => open('login')}>Already have an account? Sign in</button>}</div>
      </form>}{error && <p role="alert" className="account-error">{error}</p>}
    </section></div>}
  </div>;
}
