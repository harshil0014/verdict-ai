import React, { useEffect, useMemo, useState, lazy, Suspense } from "react";
import { createRoot } from "react-dom/client";
import {
  ReactFlow,
  Background,
  Controls,
  MarkerType,
  type Node,
  type Edge,
} from "@xyflow/react";
import {
  ArrowUpRight,
  ArrowRight,
  ArrowLeft,
  Search,
  Plus,
  FolderOpen,
  GitBranch,
  FileText,
  Clock3,
  ShieldCheck,
  Settings2,
  ChevronRight,
  Upload,
  Download,
  LoaderCircle,
  X,
  Link2,
  Check,
  AlertTriangle,
  LogOut,
  ScanLine,
  Inbox,
  Send,
  Eye,
  RefreshCw,
  Scale,
  CheckCircle2,
  ExternalLink,
} from "lucide-react";
import "@xyflow/react/dist/style.css";
import "./style.css";
import { AccountEntry } from "./saas";
import { CaseNavigation } from './case-navigation';
import { AutomaticInvestigation } from './automation';
import './research.css';
const EvidenceDiscoveries=lazy(()=>import('./research').then(m=>({default:m.EvidenceDiscoveries})));
const ResearchActivity=lazy(()=>import('./research').then(m=>({default:m.ResearchActivity})));
const FindEvidence=lazy(()=>import('./research').then(m=>({default:m.FindEvidence})));
const PublicSourceFacts=lazy(()=>import('./research').then(m=>({default:m.PublicSourceFacts})));

type Source = {
  id: string;
  title: string;
  text: string;
  party: string;
  origin: string;
  origin_verified: boolean;
  received_at: string;
  sha256: string;
  mime: string;
  synthetic: boolean;
  file_available?: boolean;
  superseded_by?: string;
  replaces_source_id?: string;
  provenance?: any;
};
type Claim = {
  id: string;
  text: string;
  source_id: string;
  quote: string;
  semantic_support: string;
  support_reason?: string;
  source_check: string;
  structured_check?: string;
  origin_verified: boolean;
  epistemic_status?: string;
  epistemic_reason?: string;
};
type Hypothesis = {
  id: string;
  title: string;
  explanation: string;
  supports: string[];
  challenges: string[];
  status: string;
};
type Witness = {
  id: string;
  title: string;
  question: string;
  recipient: string;
  distinguishes: string[];
  rationale: string;
  burden: string;
  priority: string;
};
type Analysis = {
  summary: string;
  finding: string;
  claims: Claim[];
  hypotheses: Hypothesis[];
  requests: Witness[];
  unknowns: string[];
  recommendation: string;
  comparisons: any[];
  warnings: any[];
  model: string;
  latency_seconds: number;
  created_at: string;
  change?: any;
  rejected_claims: any[];
};
type Case = {
  id: string;
  title: string;
  story: string;
  reason: string;
  mode: string;
  status: string;
  amount: string;
  currency: string;
  deadline: string | null;
  evidence: Source[];
  analysis: Analysis | null;
  analysis_stale?: boolean;
  revision: number;
  updated_at: string;
  requests: any[];
  timeline?: any[];
  audit_valid?: boolean;
  paypal_id?: string;
  paypal_snapshot?: any;
  payment_record_acquisition?: { status: string; records_read: number; issues: string[] };
  automation?: any;
};
let authGeneration = 0;
async function api(path: string, method = "GET", body?: any, token?: string) {
  if (path.startsWith('/auth/')) authGeneration++;
  const generation = authGeneration;
  const headers: any = {};
  if (body && !(body instanceof FormData))
    headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = "Bearer " + token;
  const r = await fetch("/api" + path, {
    method,
    headers,
    body:
      body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
    credentials: "same-origin",
  });
  const d = await r.json();
  if (generation !== authGeneration) throw new Error("Your session changed. Please open the case again.");
  if (!r.ok) {
    const failure = Object.assign(new Error(typeof d.detail === 'string' ? d.detail : "The request could not be completed"), {status:r.status});
    if (r.status === 401 && ((!path.startsWith('/auth/') && path !== '/me' && path !== '/portal') || path === '/auth/logout')) window.dispatchEvent(new Event('verdict-session-ended'));
    throw failure;
  }
  return d;
}
const readable = (s: string) => s.replaceAll("_", " ").replaceAll("-", " ");
const sellerEvidenceTypes = (c: Case | null): string[] =>
  ["PROOF_OF_FULFILLMENT", "OTHER"].filter(type =>
    c?.paypal_snapshot?.evidences?.some((e: any) =>
      e.source === "REQUESTED_FROM_SELLER" && e.evidence_type === type &&
      (!e.action_info?.action || e.action_info.action === "PROVIDE_EVIDENCE")));
const date = (s: string) =>
  new Date(s).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
const findings: Record<string, string> = {
  insufficient: "More evidence needed",
  conflicting: "Conflicting accounts",
  supports_buyer: "Buyer account supported",
  supports_seller: "Seller account supported",
};

function App() {
  const [config, setConfig] = useState<any>(null);
  const [me, setMe] = useState<any>(null),
    [items, setItems] = useState<Case[]>([]),
    [current, setCurrent] = useState<Case | null>(null),
    [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(""),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [tab, setTab] = useState("investigation"),
    [query, setQuery] = useState(""),
    [filter, setFilter] = useState("all"),
    [modal, setModal] = useState(""),
    [source, setSource] = useState<Source | null>(null),
    [claim, setClaim] = useState<Claim | null>(null),
    [portalLink, setPortalLink] = useState(""),
    [reviewedWitness, setReviewedWitness] = useState<Witness | null>(null),
    [integration, setIntegration] = useState<any>(null),
    [approval, setApproval] = useState<any>(null);
  const hash = new URLSearchParams(location.hash.slice(1));
  const portalToken = hash.get("request");
  const [portal, setPortal] = useState<any>(null),
    [portalDone, setPortalDone] = useState(false),
    [demoCode, setDemoCode] = useState("");
  const [closingRequest, setClosingRequest] = useState<any>(null);
  const [evidenceParty, setEvidenceParty] = useState('other');
  function clearPrivateState() {
    setItems([]); setCurrent(null); setSource(null); setClaim(null); setIntegration(null);
    setApproval(null); setPortalLink(''); setReviewedWitness(null); setClosingRequest(null);
    setModal(''); setNotice(''); setError(''); setQuery(''); setFilter('all'); setTab('investigation'); setEvidenceParty('other');
  }
  async function authenticated() {
    clearPrivateState();
    const profile = await api('/me');
    await load();
    setMe(profile);
  }
  useEffect(() => {
    const ended = () => { authGeneration++; clearPrivateState(); setMe(null); setError('Your session has ended. Sign in to return to your workspace.'); };
    window.addEventListener('verdict-session-ended', ended);
    return () => window.removeEventListener('verdict-session-ended', ended);
  }, []);
  async function run(label: string, fn: () => Promise<any>) {
    setBusy(label);
    setError("");
    try {
      return await fn();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  }
  async function load(id?: string) {
    const rows = await api("/cases");
    setItems(rows);
    const choice = [id, current?.id, rows[0]?.id].find(value => rows.some((c: Case) => c.id === value));
    setCurrent(choice ? await api("/cases/" + choice) : null);
  }
  async function choose(id: string) {
    await run("Opening case", async () => {
      setCurrent(await api("/cases/" + id));
      setTab("investigation");
      setSource(null);
      setClaim(null);
    });
  }
  async function refresh() {
    await load(current?.id);
  }
  useEffect(() => {
    (async () => {
      try {
        const settings = await api('/config');
        setConfig(settings);
        if (portalToken) {
          setPortal(await api("/portal", "GET", undefined, portalToken));
          return;
        }
        const bootstrap = hash.get("bootstrap");
        if (bootstrap && settings.auth_mode === 'legacy') {
          history.replaceState(null, "", location.pathname);
          setMe(await api("/auth/login", "POST", { bootstrap }));
          await load();
          return;
        }
        try {
          setMe(await api("/me"));
          await load();
        } catch (e: any) {
          setMe(null);
          if (e.status !== 401) throw e;
        }
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setModal("");
        setSource(null);
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);
  useEffect(() => {
    if (notice) {
      const h = setTimeout(() => setNotice(""), 8000);
      return () => clearTimeout(h);
    }
  }, [notice]);
  useEffect(() => {
    if (!current || busy || modal || source) return;
    const timer = setInterval(async () => {
      if (document.visibilityState !== "visible") return;
      try {
        const latest = await api("/cases/" + current.id);
        if (latest.revision !== current.revision || latest.automation?.updated_at !== current.automation?.updated_at) {
          setCurrent(latest);
          setItems((v) => v.map((c) => (c.id === latest.id ? latest : c)));
        }
      } catch {}
    }, ['queued','running'].includes(current.automation?.state) ? 4000 : 15000);
    return () => clearInterval(timer);
  }, [current?.id, current?.revision, current?.automation?.updated_at, busy, modal, source]);
  const a = current?.analysis;
  const totals = useMemo(
    () => ({
      open: items.length,
      requests: items.reduce(
        (n, c) => n + c.requests.filter((r) => r.status === "open").length,
        0,
      ),
      review: items.filter((c) => c.analysis && !c.analysis_stale).length,
    }),
    [items],
  );
  const rows = items.filter(
    (c) =>
      (c.title + " " + c.reason + " " + c.id)
        .toLowerCase()
        .includes(query.toLowerCase()) &&
      (filter === "all" ||
        (filter === "requests" &&
          c.requests.some((r) => r.status === "open")) ||
        (filter === "review" && c.analysis && !c.analysis_stale) ||
        (filter === "sandbox" && c.mode === "paypal_sandbox")),
  );
  const graph = useMemo(() => {
    if (!current) return { nodes: [], edges: [] };
    const nodes: Node[] = [],
      edges: Edge[] = [];
    const es = current.evidence,
      cs = a?.claims || [],
      hs = a?.hypotheses || [];
    hs.forEach((h, i) =>
      nodes.push({
        id: "h-" + h.id,
        position: { x: i * 300, y: 0 },
        data: {
          label: (
            <>
              <span className="node-kind">HYPOTHESIS · {h.status}</span>
              <strong>{h.title}</strong>
              <small>
                {h.supports.length} supporting · {h.challenges.length}{" "}
                challenging
              </small>
            </>
          ),
        },
        className: "hypothesis-node",
      }),
    );
    cs.forEach((c, i) =>
      nodes.push({
        id: "c-" + c.id,
        position: { x: (i % 4) * 250, y: 190 + Math.floor(i / 4) * 150 },
        data: {
          claim: c,
          label: (
            <>
              <span className="node-kind">REPORTED CLAIM · {c.id}</span>
              <strong>{c.text}</strong>
              <small>{readable(c.epistemic_status || 'reported claim')} · {readable(c.semantic_support)} · inspect</small>
            </>
          ),
        },
        className:
          "claim-node " +
          (c.semantic_support === "entailed" ? "" : "uncertain-node"),
      }),
    );
    const ey = hs.length ? 250 + Math.ceil(cs.length / 4) * 150 : 100;
    es.forEach((e, i) =>
      nodes.push({
        id: "e-" + e.id,
        position: { x: (i % 4) * 250, y: ey + Math.floor(i / 4) * 140 },
        data: {
          source: e,
          label: (
            <>
              <span className="node-kind">
                SOURCE · {e.party.toUpperCase()}
              </span>
              <strong>{e.title}</strong>
              <small>
                {e.origin_verified
                  ? "API origin verified"
                  : "Reported · origin unverified"}
              </small>
            </>
          ),
        },
        className: "evidence-node",
      }),
    );
    cs.forEach((c) =>
      edges.push({
        id: "s-" + c.id,
        source: "e-" + c.source_id,
        target: "c-" + c.id,
        label: "cites",
        type: "smoothstep",
        style: { stroke: "#82998d" },
        markerEnd: { type: MarkerType.ArrowClosed, color: "#82998d" },
      }),
    );
    hs.forEach((h) => {
      h.supports.forEach((id) =>
        edges.push({
          id: `sup-${h.id}-${id}`,
          source: "c-" + id,
          target: "h-" + h.id,
          label: "supports",
          type: "smoothstep",
          style: { stroke: "#278563" },
          markerEnd: { type: MarkerType.ArrowClosed, color: "#278563" },
        }),
      );
      h.challenges.forEach((id) =>
        edges.push({
          id: `con-${h.id}-${id}`,
          source: "c-" + id,
          target: "h-" + h.id,
          label: "challenges",
          type: "smoothstep",
          style: { stroke: "#c16b45", strokeDasharray: "5 4" },
          markerEnd: { type: MarkerType.ArrowClosed, color: "#c16b45" },
        }),
      );
    });
    return { nodes, edges };
  }, [current]);
  const graphClick = (_: any, node: Node) => {
    if (node.data.source) {
      setSource(node.data.source as Source);
      setClaim(null);
    }
    if (node.data.claim) {
      const c = node.data.claim as Claim;
      setClaim(c);
      setSource(current!.evidence.find((e) => e.id === c.source_id) || null);
    }
    if (node.id.startsWith("h-")) {
      const h = a?.hypotheses.find((h) => "h-" + h.id === node.id);
      if (h) setNotice(h.explanation);
    }
  };
  function field(form: HTMLFormElement, key: string) {
    return String(new FormData(form).get(key) || "");
  }
  async function analyze() {
    setModal("");
    await run("Investigating evidence", async () => {
      const c = await api(`/cases/${current!.id}/analyze`, "POST", {
        consent: true,
      });
      setCurrent(await api("/cases/" + c.id));
      await load(c.id);
      setNotice(
        "Investigation updated from the current evidence. Review source support before acting.",
      );
    });
  }
  async function createRequest(w: Witness) {
    setReviewedWitness(w);
    setModal("request-review");
  }
  async function issueRequest(form: HTMLFormElement) {
    await run("Creating secure request", async () => {
      const d = await api(`/cases/${current!.id}/requests`, "POST", {
        witness_id: reviewedWitness!.id,
        title: field(form, "title"),
        question: field(form, "question"),
        recipient: field(form, "recipient"),
      });
      setPortalLink(location.origin + "/" + d.portal_fragment);
      await refresh();
      setModal("request-link");
    });
  }
  const alert = (
    <>
      {error && (
        <div className="toast error" role="alert">
          <AlertTriangle size={17} />
          <span>{error}</span>
          <button aria-label="Dismiss error" onClick={() => setError("")}>
            <X size={16} />
          </button>
        </div>
      )}
      {notice && (
        <div className="toast" role="status">
          <CheckCircle2 size={17} />
          <span>{notice}</span>
          <button aria-label="Dismiss notice" onClick={() => setNotice("")}>
            <X size={16} />
          </button>
        </div>
      )}
    </>
  );
  if (loading)
    return (
      <div className="loading-screen">
        <div className="brand-mark">V</div>
        <LoaderCircle className="spin" />
        <span>Opening your investigation workspace…</span>
      </div>
    );
  if (portalToken)
    return (
      <div className="entry">
        <div className="entry-card">
          <Brand />
          <span className="eyebrow">SECURE EVIDENCE REQUEST</span>
          {portalDone ? (
            <>
              <CheckCircle2 size={42} />
              <h1>Witness received.</h1>
              <p>
                Your response is available to the investigator. It has not been
                independently verified. You cannot view the other party's
                evidence.
              </p>
            </>
          ) : portal ? (
            <>
              <h1>{portal.title}</h1>
              <p className="portal-question">{portal.question}</p>
              <p>
                Requested from: <strong>{portal.recipient}</strong> · Expires{" "}
                {new Date(portal.expires_at * 1000).toLocaleDateString()}
              </p>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const f = e.currentTarget;
                  run("Sending response", async () => {
                    await api(
                      "/portal",
                      "POST",
                      {
                        title: field(f, "title"),
                        text: field(f, "text"),
                        party: "other",
                      },
                      portalToken,
                    );
                    setPortalDone(true);
                  });
                }}
              >
                <label>
                  Document or response title
                  <input name="title" required maxLength={160} />
                </label>
                <label>
                  Your evidence
                  <textarea name="text" required maxLength={30000} rows={7} />
                </label>
                <p className="fine">
                  Share only evidence you have permission to provide. The
                  investigator can see your response and may investigate it with Gemini and retrieve its safe public references automatically. This link gives access
                  only to this request.
                </p>
                <button className="primary" disabled={!!busy}>
                  <Send size={16} />
                  Submit evidence
                </button>
              </form>
              <label className="upload-alt">
                Or submit a TXT, JSON or text PDF
                <input
                  type="file"
                  accept=".txt,.json,.pdf"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f)
                      run("Uploading evidence", async () => {
                        const d = new FormData();
                        d.set("file", f);
                        await api("/portal/upload", "POST", d, portalToken);
                        setPortalDone(true);
                      });
                  }}
                />
              </label>
            </>
          ) : (
            <>
              <h1>Request unavailable</h1>
              <p>The request may have expired or already been answered.</p>
            </>
          )}
          {alert}
        </div>
      </div>
    );
  if (!me)
    if (!config) return <div className="loading-screen"><h1>Workspace temporarily unavailable</h1><p>{error || 'Unable to load account configuration.'}</p><button className="primary" onClick={() => location.reload()}>Try again</button></div>;
    else if (config.auth_mode === 'account') return <><AccountEntry api={api} onAuthenticated={authenticated}/>{alert}</>;
  if (!me)
    return (
      <div className="entry">
        <div className="entry-art">
          <div className="art-grid" />
          <span className="eyebrow">THE MISSING WITNESS</span>
          <h1>
            Every story has
            <br />a missing piece.
          </h1>
          <p>
            Don't automate the argument.
            <br />
            Find the missing evidence.
          </p>
          <div className="art-orbit">
            <span>BUYER</span>
            <i />
            <b>?</b>
            <i />
            <span>SELLER</span>
          </div>
          <small>VERDICT · EVIDENCE BEFORE CERTAINTY</small>
        </div>
        <div className="entry-card">
          <Brand />
          <span className="eyebrow">INVESTIGATION WORKSPACE</span>
          <h1>
            A clearer picture
            <br />
            starts here.
          </h1>
          <p>
            Investigate competing accounts. Find the next useful witness. Keep
            the human in the decision.
          </p>
          <label className="demo-code">
            Judge access code (hosted demo only)
            <input
              type="password"
              value={demoCode}
              onChange={(e) => setDemoCode(e.target.value)}
              autoComplete="off"
              placeholder="Leave blank for local exploration"
            />
          </label>
          <button
            className="primary large"
            disabled={!!busy}
            onClick={() =>
              run("Opening fictional workspace", async () => {
                setMe(await api("/auth/demo", "POST", { code: demoCode }));
                await load();
              })
            }
          >
            Explore fictional cases <ArrowRight size={18} />
          </button>
          <p className="fine">
            Isolated demo workspace · Real Gemini analysis when requested · No
            PayPal actions
          </p>
          <div className="divider">OPERATOR ACCESS</div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const p = field(e.currentTarget, "password");
              run("Signing in", async () => {
                setMe(await api("/auth/login", "POST", { password: p }));
                await load();
              });
            }}
          >
            <label>
              Operator password
              <input
                type="password"
                name="password"
                autoComplete="current-password"
                required
              />
            </label>
            <button className="secondary" disabled={!!busy}>
              Sign in <ArrowUpRight size={16} />
            </button>
          </form>
          <p className="fine">
            For local operator access, use Launch VERDICT. Public demo access
            never exposes the operator's sandbox records.
          </p>
          {alert}
        </div>
      </div>
    );
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Brand />
        <div className="workspace">
          <div className="workspace-icon">V</div>
          <div>
            <strong>Investigation studio</strong>
            <small>
              {me.role === "operator"
                ? "Private operator workspace"
                : me.role === "member" ? "Your private cloud workspace"
                : "Isolated fictional workspace"}
            </small>
          </div>
        </div>
        <span className="nav-caption">WORKSPACE</span>
        <nav>
          <button
            className={tab === "investigation" ? "active" : ""}
            onClick={() => setTab("investigation")}
          >
            <FolderOpen size={18} />
            Case investigations<span>{totals.open}</span>
          </button>
          <button
            className={tab === "requests" ? "active" : ""}
            onClick={() => setTab("requests")}
          >
            <ScanLine size={18} />
            Witness requests<span>{totals.requests}</span>
          </button>
          <button
            className={tab === "evidence" ? "active" : ""}
            onClick={() => setTab("evidence")}
          >
            <FileText size={18} />
            Evidence library
          </button>
          <button
            className={tab === "timeline" ? "active" : ""}
            onClick={() => setTab("timeline")}
          >
            <Clock3 size={18} />
            Investigation trail
          </button>
        </nav>
        <div className="sidebar-note">
          <div className="live-dot" />
          <span>
            Human judgment.
            <br />
            <strong>Better evidence.</strong>
          </span>
          <p>AI assessments are reviewable. Decisions stay with you.</p>
        </div>
        <button
          className="sidebar-bottom"
          onClick={() => {
            if (me.role === "operator" || me.role === "member")
              run("Checking integrations", async () => {
                if (me.role === 'member') setMe(await api('/me'));
                setIntegration(await api("/integrations"));
                setModal("integrations");
              });
            else {
              setIntegration(null);
              setModal("integrations");
            }
          }}
        >
          <Settings2 size={17} />
          Connections & safeguards
        </button>
        <button
          className="identity"
          onClick={() =>
            run("Signing out", async () => {
              await api("/auth/logout", "POST");
              setMe(null);
              clearPrivateState();
            })
          }
        >
          <span className="avatar">{me.role === "operator" ? "OP" : me.role === "member" ? me.user.display_name.slice(0,2).toUpperCase() : "DE"}</span>
          <span>
            <strong>
              {me.role === "operator" ? "Operator" : me.role === "member" ? me.user.display_name : "Demo investigator"}
            </strong>
            <small>Sign out</small>
          </span>
          <LogOut size={16} />
        </button>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div>
            <span>Workspace</span>
            <ChevronRight size={14} />
            <strong>Case investigations</strong>
          </div>
          <span className="sandbox-tag">
            <span className="live-dot" />
            {me.role === "operator" ? "SANDBOX ONLY" : me.role === "member" ? "PRIVATE WORKSPACE" : "FICTIONAL DATA"}
          </span>
          <button
            className="secondary small"
            onClick={() => setModal("new-case")}
          >
            <Plus size={15} />
            New case
          </button>
        </header>
        <main>
          {me.role === 'member' && <div className="account-mobile"><strong>{me.user.display_name}</strong><button onClick={() => run('Checking account',async () => {setMe(await api('/me'));setIntegration(await api('/integrations'));setModal('integrations');})}>Safeguards</button><button onClick={() => run('Signing out',async () => {await api('/auth/logout','POST');setMe(null);clearPrivateState();})}>Sign out <LogOut size={13}/></button></div>}
          {me.ephemeral_storage && (
            <div className="consent-box" role="note">
              <AlertTriangle size={20} />
              <p>Temporary demo workspace. Use fictional records only. Cases and request links can disappear when this free host restarts; export work you want to keep.</p>
            </div>
          )}
          <div className="page-heading">
            <div>
              <span className="eyebrow">EVIDENCE BEFORE CERTAINTY</span>
              <h1>
                The investigation room<span>.</span>
              </h1>
              <p>
                Follow the facts. Question the gaps. Find the missing witness.
              </p>
            </div>
            {me.role !== "member" && <button
              className="secondary"
              disabled={!!busy || me.role !== "operator"}
              title={
                me.role !== "operator"
                  ? "Operator access required"
                  : "Retrieve actual sandbox disputes"
              }
              onClick={() =>
                run("Syncing PayPal sandbox", async () => {
                  const r = await api("/paypal/sync", "POST");
                  await load();
                  setNotice(r.message);
                })
              }
            >
              <RefreshCw
                size={16}
                className={busy === "Syncing PayPal sandbox" ? "spin" : ""}
              />
              Sync PayPal
            </button>}
          </div>
          <section className="metrics">
            <div>
              <span>Open investigations</span>
              <strong>{String(totals.open).padStart(2, "0")}</strong>
              <small>
                In this workspace <FolderOpen size={15} />
              </small>
            </div>
            <div>
              <span>Outstanding witnesses</span>
              <strong>{String(totals.requests).padStart(2, "0")}</strong>
              <small>
                Evidence requests awaiting reply <ScanLine size={15} />
              </small>
            </div>
            <div>
              <span>Ready for human review</span>
              <strong>{String(totals.review).padStart(2, "0")}</strong>
              <small>
                Current analysis available <ShieldCheck size={15} />
              </small>
            </div>
            <div className="metric-principle">
              <Scale size={24} />
              <strong>
                Two sides.
                <br />
                One evidence record.
              </strong>
              <small>Source integrity ≠ factual truth</small>
            </div>
          </section>
          <div className="case-workspace">
            <section className="case-queue">
              <div className="queue-heading">
                <h2>
                  Case inbox <span>{rows.length}</span>
                </h2>
                <button
                  aria-label="Create a case"
                  onClick={() => setModal("new-case")}
                >
                  <Plus size={17} />
                </button>
              </div>
              <label className="search">
                <Search size={16} />
                <input
                  placeholder="Search investigations…"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </label>
              <select
                className="filter"
                aria-label="Filter cases"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              >
                <option value="all">All investigations</option>
                <option value="requests">Awaiting witness</option>
                <option value="review">Ready for review</option>
                {me.role !== "member" && <option value="sandbox">PayPal sandbox</option>}
              </select>
              <div className="case-list">
                {rows.map((c) => (
                  <button
                    key={c.id}
                    className={
                      "case-row " + (c.id === current?.id ? "selected" : "")
                    }
                    onClick={() => choose(c.id)}
                  >
                    <div className="case-row-top">
                      <span>
                        {c.mode === "paypal_sandbox"
                          ? "PAYPAL SANDBOX"
                          : c.mode === "synthetic"
                            ? "FICTIONAL CASE"
                            : "MANUAL CASE"}
                      </span>
                      <strong>
                        {c.currency} {c.amount}
                      </strong>
                    </div>
                    <h3>{c.title}</h3>
                    <p>{readable(c.reason)}</p>
                    <div className="case-row-bottom">
                      <span
                        className={"status " + (c.analysis ? "assessed" : "")}
                      >
                        <i />
                        {c.analysis_stale
                          ? "New evidence"
                          : c.analysis
                            ? findings[c.analysis.finding]
                            : "Not investigated"}
                      </span>
                      <ChevronRight size={14} />
                    </div>
                  </button>
                ))}
                {!rows.length && (
                  <div className="empty-small">No cases match this view.</div>
                )}
              </div>
              <div className="queue-footer">
                <ShieldCheck size={14} />
                Evidence stays within this workspace
              </div>
            </section>
            {current ? (
              <section className="case-detail">
                <div className="case-heading">
                  <div>
                    <div className="case-kicker">
                      <span className="pill">
                        {current.mode === "synthetic"
                          ? "FICTIONAL SCENARIO"
                          : readable(current.mode).toUpperCase()}
                      </span>
                      <span>REV {current.revision}</span>
                    </div>
                    <h2>{current.title}</h2>
                    <p>{current.story}</p>
                  </div>
                  <div className="case-amount">
                    <strong>
                      {current.currency} {current.amount}
                    </strong>
                    <span>
                      {current.deadline
                        ? "Due " + date(current.deadline)
                        : "No provider deadline supplied"}
                    </span>
                  </div>
                </div>
                <div className="case-tabs">
                  <CaseNavigation tab={tab} evidenceCount={current.evidence.length} witnessCount={current.requests.length} onSelect={setTab}/>
                  <button
                    className="export"
                    title="Export case record"
                    onClick={() => {
                      location.href = "/api/cases/" + current.id + "/export";
                    }}
                  >
                    <Download size={16} />
                  </button>
                </div>
                {me.role === 'member' && ['investigation','timeline'].includes(tab) && <>
                  <AutomaticInvestigation key={current.id+'-automation'} current={current} api={api} changed={refresh}/>
                  <Suspense fallback={<p className="fine">Loading source retrieval history…</p>}><ResearchActivity key={current.id+'-activity'} caseId={current.id} revision={current.revision} activityVersion={current.automation?.updated_at} api={api} changed={refresh}/></Suspense>
                </>}
                {busy && (
                  <div className="progress" role="status">
                    <LoaderCircle size={16} className="spin" />
                    {busy}…
                    {busy === "Investigating evidence" && (
                      <span>
                        Extracting claims → checking quotes → assessing semantic
                        support
                      </span>
                    )}
                  </div>
                )}
                {current.analysis_stale && (
                  <div className="stale">
                    <AlertTriangle size={16} />
                    New evidence has arrived. The previous investigation is
                    shown while VERDICT updates the investigation.
                    {!['queued','running'].includes(current.automation?.state)&&<button onClick={() => setModal("analyze")}>
                      Reassess <ArrowRight size={14} />
                    </button>}
                  </div>
                )}
                {tab === "investigation" && (
                  <>
                    <div className="investigation-tools">
                      <div>
                        <span className="eyebrow">THE EVIDENCE NETWORK</span>
                        <h3>
                          {a
                            ? findings[a.finding]
                            : "What does the evidence actually establish?"}
                        </h3>
                      </div>
                      <button
                        className="primary"
                        disabled={!!busy || ['queued','running'].includes(current.automation?.state)}
                        onClick={() => setModal("analyze")}
                      >
                        <ScanLine size={16} />
                        {['queued','running'].includes(current.automation?.state) ? 'Investigation in progress' : a ? "Reassess case" : "Investigate case"}
                      </button>
                    </div>
                    <div className="investigation-grid">
                      <div className="graph-panel">
                        <div className="graph-header">
                          <span>
                            <GitBranch size={16} />
                            Living investigation
                          </span>
                          <span>
                            {a
                              ? `${a.claims.length} claims · ${a.hypotheses.length} explanations`
                              : `${current.evidence.length} sources · analysis pending`}
                          </span>
                        </div>
                        <div className="graph">
                          <ReactFlow
                            key={current.id + "-" + (a?.created_at || "empty")}
                            nodes={graph.nodes}
                            edges={graph.edges}
                            fitView
                            fitViewOptions={{ padding: 0.22 }}
                            minZoom={0.15}
                            maxZoom={1.5}
                            onNodeClick={graphClick}
                            nodesConnectable={false}
                            nodesDraggable={false}
                            proOptions={{ hideAttribution: false }}
                          >
                            <Background color="#ccd6ce" gap={20} />
                            <Controls showInteractive={false} />
                          </ReactFlow>
                          {!a && (
                            <div className="graph-prompt">
                              <ScanLine size={22} />
                              <strong>
                                The sources are here.
                                <br />
                                The investigation starts with a question.
                              </strong>
                              <p>
                                Run an investigation to extract claims, compare
                                explanations and find the next useful witness.
                              </p>
                            </div>
                          )}
                        </div>
                        <div className="graph-legend">
                          <span>
                            <i className="legend-source" />
                            Evidence
                          </span>
                          <span>
                            <i className="legend-claim" />
                            Reported claim
                          </span>
                          <span>
                            <i className="legend-hypothesis" />
                            Explanation
                          </span>
                          <small>Select a node to inspect its source</small>
                        </div>
                      </div>
                      <aside className="witness-panel">
                        <div className="witness-label">
                          <ScanLine size={18} />
                          THE MISSING WITNESS
                        </div>
                        {a?.requests.length ? (
                          (() => {
                            const w =
                              a.requests.find((w) => w.priority === "first") ||
                              a.requests[0];
                            return (
                              <>
                                <span className="ordinal">
                                  NEXT BEST QUESTION
                                </span>
                                <h3>{w.title}</h3>
                                <p>{w.question}</p>
                                <div className="witness-meta">
                                  <span>
                                    Ask the <strong>{w.recipient}</strong>
                                  </span>
                                  <span>{w.burden} burden</span>
                                </div>
                                <div className="why">
                                  <span>WHY THIS MATTERS</span>
                                  <p>{w.rationale}</p>
                                  <small>
                                    Distinguishes {w.distinguishes.length}{" "}
                                    competing explanations
                                  </small>
                                </div>
                                <button
                                  disabled={!!busy || !!current.analysis_stale}
                                  onClick={() => createRequest(w)}
                                >
                                  Create evidence request{" "}
                                  <ArrowUpRight size={17} />
                                </button>
                                <small className="witness-fine">
                                  Creates a restricted response link. Nothing is
                                  sent automatically.
                                </small>
                              </>
                            );
                          })()
                        ) : (
                          <>
                            <span className="ordinal">FOLLOW THE GAP</span>
                            <h3>
                              {a
                                ? "No further targeted request proposed."
                                : "The right question changes the case."}
                            </h3>
                            <p>
                              {a
                                ? "Review the evidence and remaining unknowns. An unresolved outcome is legitimate."
                                : "An investigation identifies what would distinguish the buyer’s account from the seller’s. It does not assume either is right."}
                            </p>
                            <div className="witness-empty">
                              <ScanLine size={52} />
                              <span>
                                {a
                                  ? "Human review remains required"
                                  : "Awaiting investigation"}
                              </span>
                            </div>
                          </>
                        )}
                      </aside>
                    </div>
                    {a && (
                      <div className="findings-grid">
                        <div className="finding-summary">
                          <span className="eyebrow">CURRENT ASSESSMENT</span>
                          <h3>{findings[a.finding]}</h3>
                          <p>{a.summary}</p>
                          {a.change && (
                            <div className="change-note">
                              <RefreshCw size={15} />
                              Reassessment:{" "}
                              {findings[a.change.previous_finding]} →{" "}
                              {findings[a.change.current_finding]}.{" "}
                              {a.change.new_source_ids.length} newly cited
                              sources.
                            </div>
                          )}
                          <small>
                            AI assessment · {a.model} · {a.latency_seconds}s ·{" "}
                            {date(a.created_at)}
                          </small>
                        </div>
                        <div className="unknowns">
                          <span className="eyebrow">STILL UNKNOWN</span>
                          {a.unknowns.map((u, i) => (
                            <p key={i}>
                              <span>{String(i + 1).padStart(2, "0")}</span>
                              {u}
                            </p>
                          ))}
                          {!a.unknowns.length && (
                            <p>
                              No additional unknowns identified by the model.
                              Human verification is still required.
                            </p>
                          )}
                        </div>
                      </div>
                    )}
                    {!!a?.comparisons.length && (
                      <div className="comparisons">
                        <span className="eyebrow">
                          REPORTED FIELD DISCREPANCIES
                        </span>
                        {a.comparisons.map((x: any) => (
                          <div key={x.id}>
                            <AlertTriangle size={17} />
                            <p>
                              {x.description}
                              <small>{x.verification}</small>
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                    {!!a?.warnings.length && (
                      <div className="stale">
                        <ShieldCheck size={18} />
                        {a.warnings.length} source(s) contain instruction-like
                        language. Content was treated as data; the model has no
                        action tools.
                      </div>
                    )}
                  </>
                )}
                {tab === "evidence" && (
                  <div className="tab-content">
                    <div className="section-heading">
                      <div>
                        <span className="eyebrow">THE SOURCE RECORD</span>
                        <h3>Every claim starts somewhere.</h3>
                      </div>
                      <div className="evidence-heading-actions">
                      {me.role==='member'&&<button className="secondary" onClick={()=>setModal('find-evidence')}><Search size={16}/> Find more evidence</button>}
                      <button
                        className="primary"
                        onClick={() => setModal("evidence")}
                      >
                        <Upload size={16} />
                        Add evidence
                      </button>
                      </div>
                    </div>
                    <div className="source-list">
                      {current.evidence.map((e, i) => (
                        <article className="evidence-source" key={e.id}><button
                          onClick={() => {
                            setSource(e);
                            setClaim(null);
                          }}
                        >
                          <span className="file-icon">
                            <FileText size={21} />
                          </span>
                          <div>
                            <strong>{e.title}{e.superseded_by ? " · historical snapshot" : ""}</strong>
                            <small>
                              {e.party} · {readable(e.origin)} ·{" "}
                              {date(e.received_at)}
                            </small>
                            <span className="source-origin">
                              {e.origin_verified
                                ? "API origin verified · contents still require assessment"
                                : "Origin not independently verified"}
                            </span>
                          </div>
                          <span className="mono">
                            {String(i + 1).padStart(2, "0")}
                          </span>
                          <ArrowUpRight size={17} />
                        </button>{e.provenance&&<Suspense fallback={<p className="fine">Loading source provenance…</p>}><PublicSourceFacts source={e}/></Suspense>}</article>
                      ))}
                    </div>
                    {me.role==='member'&&<Suspense fallback={<p className="fine">Loading retained discoveries…</p>}><EvidenceDiscoveries key={current.id+'-discoveries'} caseId={current.id} revision={current.revision} activityVersion={current.automation?.updated_at} api={api} changed={refresh} evidenceIds={current.evidence.map(e=>e.id)}/></Suspense>}
                    {!current.evidence.length && (
                      <Empty
                        title="No evidence yet"
                        text="Add a source before beginning an investigation."
                      />
                    )}
                    <div className="principle-note">
                      <ShieldCheck size={18} />
                      <p>
                        A stored file and a matching hash establish integrity
                        after ingestion. They do not establish factual truth.
                      </p>
                    </div>
                  </div>
                )}
                {tab === "requests" && (
                  <div className="tab-content">
                    <div className="section-heading">
                      <div>
                        <span className="eyebrow">EVIDENCE ACQUISITION</span>
                        <h3>A question with a purpose.</h3>
                      </div>
                      {me.role === 'member' && <button className="secondary" onClick={() => createRequest({id:'manual',title:'',question:'',recipient:'other',distinguishes:[],rationale:'Investigator-created request',burden:'medium',priority:'first'})}><Plus size={16}/> New request</button>}
                      <button
                        className="secondary"
                        onClick={() => setModal("evidence")}
                      >
                        <Upload size={16} />
                        Add a response
                      </button>
                    </div>
                    {current.requests.map((r) => (
                      <div className="request-card" key={r.id}>
                        <div>
                          <span
                            className={
                              "status " +
                              (r.status === "received" ? "assessed" : "")
                            }
                          >
                            <i />
                            {r.status === "open" &&
                            r.expires_at * 1000 < Date.now()
                              ? "expired"
                              : r.status === "unavailable" ? "reported unavailable" : r.status}
                          </span>
                          <small>
                            {r.recipient} · {date(r.created_at)}
                          </small>
                        </div>
                        <h3>{r.title}</h3>
                        <p>{r.question}</p>
                        {r.closure_reason && (
                          <>
                            <p>Investigator report: {r.closure_reason}</p>
                            <p className="fine">{r.status === "unavailable" ? "Record availability has not been independently verified." : "The request was withdrawn and its response link revoked."}</p>
                          </>
                        )}
                        <span className="fine">
                          The restricted link was shown once when created. No
                          email was sent.
                        </span>
                        {r.status === "open" && (
                          <button className="secondary small" disabled={!!busy} onClick={() => {
                            setClosingRequest({ ...r, caseId: current.id });
                            setModal("close-request");
                          }}>Close and revoke link</button>
                        )}
                      </div>
                    ))}
                    {!current.requests.length && (
                      <Empty
                        title="No witness requests yet"
                        text="Investigate the case to identify specific evidence that could distinguish competing explanations."
                      />
                    )}
                    {a?.requests.map((w) => (
                      <div className="request-card suggested" key={w.id}>
                        <span className="eyebrow">
                          SUGGESTED · {w.priority}
                        </span>
                        <h3>{w.title}</h3>
                        <p>{w.question}</p>
                        <p className="fine">{w.rationale}</p>
                        <button
                          className="secondary"
                          disabled={!!busy || !!current.analysis_stale}
                          onClick={() => createRequest(w)}
                        >
                          Create restricted response link{" "}
                          <ArrowUpRight size={16} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                {tab === "timeline" && (
                  <div className="tab-content">
                    <div className="section-heading">
                      <div>
                        <span className="eyebrow">AN ACCOUNTABLE PROCESS</span>
                        <h3>The investigation, on record.</h3>
                      </div>
                      <span className="pill">
                        <ShieldCheck size={14} />
                        {current.audit_valid
                          ? "Integrity check passed"
                          : "Check required"}
                      </span>
                    </div>
                    <p className="fine">
                      Hash-linked local audit events detect changes within this
                      record. They are not an externally anchored or
                      tamper-proof ledger.
                    </p>
                    <div className="timeline">
                      {current.timeline?.map((e, i) => (
                        <div className="timeline-event" key={e.seq}>
                          <span className="timeline-dot">
                            {e.kind === "investigation_updated" ? (
                              <ScanLine size={15} />
                            ) : (
                              <FileText size={15} />
                            )}
                          </span>
                          <div>
                            <small>{date(e.at)}</small>
                            <h3>{readable(e.kind)}</h3>
                            <p>
                              {e.data.title ||
                                e.data.question ||
                                (e.data.finding && findings[e.data.finding]) ||
                                e.data.status ||
                                "Case state recorded"}
                            </p>
                            <span className="mono">
                              SHA256 {e.hash.slice(0, 18)}…
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {tab === "review" && (
                  <div className="tab-content">
                    <div className="section-heading">
                      <div>
                        <span className="eyebrow">HUMAN IN THE DECISION</span>
                        <h3>Review before you respond.</h3>
                      </div>
                      <ShieldCheck size={24} />
                    </div>
                    {a ? (
                      <>
                        <div className="review-recommendation">
                          <span className="eyebrow">RECOMMENDED NEXT STEP</span>
                          <p>{a.recommendation}</p>
                        </div>
                        <h4>Source and claim checks</h4>
                        {a.claims.map((c) => (
                          <button
                            className="claim-review"
                            key={c.id}
                            onClick={() => {
                              setClaim(c);
                              setSource(
                                current.evidence.find(
                                  (e) => e.id === c.source_id,
                                ) || null,
                              );
                            }}
                          >
                            <div>
                              <span className="mono">{c.id}</span>
                              <strong>{c.text}</strong>
                            </div>
                            <span
                              className={
                                "support " +
                                (c.semantic_support === "entailed"
                                  ? "supported"
                                  : "")
                              }
                            >
                              {readable(c.semantic_support)}
                            </span>
                            <ArrowUpRight size={16} />
                          </button>
                        ))}
                        {!!a.rejected_claims.length && (
                          <p className="stale">
                            {a.rejected_claims.length} claims were removed
                            because a citation could not be validated.
                          </p>
                        )}
                        <p className="fine">
                          Exact quotation, structured comparison and semantic
                          support are separate checks. Semantic support is model
                          assessed; it does not independently verify the
                          real-world event. Read sources before relying on the
                          summary or recommendation.
                        </p>
                      </>
                    ) : (
                      <Empty
                        title="No assessment to review"
                        text="Add evidence and run an investigation first."
                      />
                    )}
                    {current.mode === "paypal_sandbox" ? (
                      <div className="paypal-review">
                        <h3>PayPal sandbox response</h3>
                        <p>
                          Actions are bound to the exact payload, evidence
                          revision and current PayPal state. Every execution
                          requires a separate explicit review.
                        </p>
                        {current.payment_record_acquisition && <p className="fine">
                          Payment-record acquisition: {readable(current.payment_record_acquisition.status)} · {current.payment_record_acquisition.records_read} records read.
                          {current.payment_record_acquisition.issues.length > 0 && " Some records could not be refreshed. Review the available sources before relying on them."}
                        </p>}
                        <button
                          className="secondary"
                          onClick={() =>
                            run("Linking payment records", async () => {
                              const linked = await api(
                                `/cases/${current.id}/paypal/link-payment`,
                                "POST",
                              );
                              await refresh();
                              setNotice(`Payment-record acquisition: ${readable(linked.payment_record_acquisition?.status || "no eligible capture")}. Unchanged snapshots are not duplicated.`);
                            })
                          }
                        >
                          Refresh capture & order
                        </button>
                        <button
                          className="secondary"
                          disabled={!a || !!current.analysis_stale}
                          onClick={() => setModal("action")}
                        >
                          Prepare sandbox action <ArrowRight size={16} />
                        </button>
                        <p className="fine">
                          Execution{" "}
                          {me.sandbox_actions_enabled
                            ? "enabled"
                            : "disabled by server configuration"}
                          . No automatic financial actions.
                        </p>
                      </div>
                    ) : (
                      <div className="principle-note">
                        <Scale size={20} />
                        <p>
                          This{" "}
                          {current.mode === "synthetic"
                            ? "fictional"
                            : "manual"}{" "}
                          case cannot execute PayPal actions. Only disputes
                          retrieved from the sandbox can enter provider review.
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </section>
            ) : (
              me.role === 'member' ? <section className="onboarding"><span className="eyebrow">WELCOME, {me.user.display_name.toUpperCase()}</span><h2>Your next investigation starts here.</h2><p>This is your private workspace. Create a case and bring your own records; nothing is pre-filled.</p><ol><li>Create a case with the question you need to resolve.</li><li>Add original evidence or notes from each party.</li><li>Investigate, inspect the sources and ask for missing evidence.</li></ol><button className="primary" onClick={() => setModal('new-case')}><Plus size={17}/> Create your first case</button><p className="fine">Cloud storage · 20 MB original files · 50 cases · 10 investigation attempts/day. Shared service capacity limits apply.</p></section> : <Empty
                title="Your inbox is empty"
                text="Create a case or synchronize the PayPal sandbox."
              />
            )}
          </div>
          <footer>
            VERDICT <span>THE MISSING WITNESS</span>
            <small>
              Investigative assistance. Human decisions. No win-rate
              predictions.
            </small>
          </footer>
        </main>
      </div>
      {alert}
      {source && (
        <div className="drawer-backdrop" onClick={() => setSource(null)}>
          <aside
            className="source-drawer"
            onClick={(e) => e.stopPropagation()}
            aria-label="Evidence source inspector"
          >
            <button
              className="close"
              onClick={() => setSource(null)}
              aria-label="Close source inspector"
            >
              <X />
            </button>
            <span className="eyebrow">SOURCE INSPECTOR</span>
            <h2>{source.title}</h2>
            <div className="source-tags">
              <span className="pill">{source.party}</span>
              <span className="pill">
                {source.origin_verified
                  ? "API origin verified"
                  : "Origin unverified"}
              </span>
            </div>
            {source.superseded_by && <div className="claim-inspection">
              <strong>Historical API snapshot</strong>
              <p>A newer snapshot supersedes this record. Its original content is retained for review and excluded from new investigations.</p>
              <button className="secondary small" disabled={!current?.evidence.some(e => e.id === source.superseded_by)} onClick={() => {
                const newer = current?.evidence.find(e => e.id === source.superseded_by);
                if (newer) { setSource(newer); setClaim(null); }
              }}>Open newer snapshot</button>
            </div>}
            {claim && (
              <div className="claim-inspection">
                <span className="eyebrow">{readable(claim.epistemic_status || 'reported claim').toUpperCase()} · {claim.id}</span>
                <h3>{claim.text}</h3>
                <dl>
                  <dt>Source existence</dt>
                  <dd>{readable(claim.source_check)}</dd>
                  <dt>Structured value</dt>
                  <dd>
                    {readable(
                      claim.structured_check ||
                        "not assessed in prior revision",
                    )}
                  </dd>
                  <dt>Semantic support</dt>
                  <dd>{readable(claim.semantic_support)} · AI assessed</dd>
                </dl>
                <p>{claim.support_reason}</p>
                {claim.epistemic_reason && <p><strong>Classification review:</strong> {claim.epistemic_reason}</p>}
                <blockquote>{claim.quote}</blockquote>
              </div>
            )}
            {source.provenance && <div className="source-provenance"><strong>PRESERVED PUBLIC SOURCE</strong><a className="research-url" href={source.provenance.final_url} target="_blank" rel="noreferrer">{source.provenance.final_url} ↗</a><p>Retrieved: {date(source.provenance.retrieved_at)}<br/>Source-stated publication: {source.provenance.publication_date || 'Unknown — not inferred'}<br/>Document classification: {readable(source.provenance.source_kind)}<br/>Collection review: {readable(source.provenance.review_status || 'not recorded')}<br/>{source.provenance.classification_basis}</p>{source.provenance.parent_reference&&<p>Collected from a reference in {source.provenance.parent_reference.parent_source_id}{source.provenance.parent_reference.page&&` · PDF page ${source.provenance.parent_reference.page}`}.</p>}<p>Historical applicability is not established by retrieval. {source.provenance.event_date && `Relevant event: ${source.provenance.event_date}. `}{source.provenance.historical_note}</p>{source.provenance.excerpt_truncated&&<p>Only the first 30,000 extracted characters were investigated. Download the original for full review.</p>}<p>Extracted-text SHA-256<br/><code>{source.provenance.text_sha256}</code></p></div>}
            <span className="eyebrow">ORIGINAL EXTRACTED CONTENT</span>
            <pre>{source.text}</pre>
            {source.file_available && current && (
              <a
                className="secondary"
                href={"/api/cases/" + current.id + "/files/" + source.id}
              >
                <Download size={15} />
                Download original document
              </a>
            )}
            <dl className="source-metadata">
              <dt>Received</dt>
              <dd>{date(source.received_at)}</dd>
              <dt>Origin</dt>
              <dd>{readable(source.origin)}</dd>
              <dt>SHA-256</dt>
              <dd className="mono">{source.sha256}</dd>
            </dl>
            <p className="fine">
              Submitter identity and real-world claims have not been
              independently authenticated by VERDICT. Hashing supports
              integrity, not truth.
            </p>
          </aside>
        </div>
      )}
      {modal && (
        <div className="modal-backdrop" onClick={() => setModal("")}>
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label={readable(modal)}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="close"
              aria-label="Close dialog"
              onClick={() => setModal("")}
            >
              <X size={20} />
            </button>
            {modal === "analyze" && (
              <>
                <span className="eyebrow">A REVIEWABLE INVESTIGATION</span>
                <h2>
                  {a
                    ? "Reassess with the latest evidence"
                    : "Let the evidence speak."}
                </h2>
                <p>
                  VERDICT will send this case’s evidence to Gemini, extract
                  source-linked claims, compare explanations, and assess which
                  witness would help next.
                </p>
                <div className="consent-box">
                  <ShieldCheck size={22} />
                  <p>
                    {current?.evidence.length} source(s) · {MODEL_NAME(me)}
                    <br />
                    <small>
                      Only submit records you have permission to share with
                      Google. Free-tier processing may be used to improve Google
                      products. AI assessments can be wrong.
                    </small>
                  </p>
                </div>
                <p className="fine">
                  This operation does not send messages, submit a PayPal
                  response, or move money.
                </p>
                <button className="primary large" onClick={analyze}>
                  I authorize this analysis <ArrowRight size={17} />
                </button>
              </>
            )}
            {modal==='find-evidence'&&current&&me.role==='member'&&<Suspense fallback={<p>Opening evidence discovery…</p>}><FindEvidence caseId={current.id} api={api} suggestions={(a?.requests||[]).filter((w:any)=>w.publicly_obtainable)} completed={async()=>{await refresh();setModal('');setTab('evidence');setNotice('Sources and retrieval attempts saved. VERDICT will update the investigation automatically.');}}/></Suspense>}
            {modal === "new-case" && (
              <>
                <span className="eyebrow">START WITH THE RECORD</span>
                <h2>Open an investigation.</h2>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const f = e.currentTarget;
                    run("Creating case", async () => {
                      const c = await api("/cases", "POST", {
                        title: field(f, "title"),
                        reason: field(f, "reason"),
                        amount: field(f, "amount"),
                        currency: field(f, "currency"),
                      });
                      await load(c.id);
                      setModal("");
                      setTab("evidence");
                    });
                  }}
                >
                  <label>
                    Case title
                    <input
                      name="title"
                      required
                      minLength={3}
                      maxLength={160}
                    />
                  </label>
                  <label>
                    Dispute reason
                    <select name="reason">
                      {[
                        "ITEM_NOT_RECEIVED",
                        "SIGNIFICANTLY_NOT_AS_DESCRIBED",
                        "DUPLICATE_TRANSACTION",
                        "CREDIT_NOT_PROCESSED",
                        "OTHER",
                      ].map((s) => (
                        <option key={s} value={s}>
                          {readable(s)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="form-row">
                    <label>
                      Amount
                      <input
                        name="amount"
                        defaultValue="0.00"
                        required
                        pattern="[0-9]{1,9}\.[0-9]{2}"
                      />
                    </label>
                    <label>
                      Currency
                      <input
                        name="currency"
                        defaultValue="USD"
                        required
                        pattern="[A-Z]{3}"
                        maxLength={3}
                      />
                    </label>
                  </div>
                  <button className="primary" disabled={!!busy}>
                    Create case <Plus size={16} />
                  </button>
                </form>
              </>
            )}
            {modal === "close-request" && closingRequest && (
              <>
                <span className="eyebrow">UPDATE WITNESS AVAILABILITY</span>
                <h2>Close this request.</h2>
                <p>{closingRequest.question}</p>
                <p>The response link will stop accepting submissions. Your reason is recorded as an investigator report. It does not establish what happened in the dispute.</p>
                <form onSubmit={(e) => {
                  e.preventDefault();
                  const f = e.currentTarget;
                  run("Closing witness request", async () => {
                    await api(`/cases/${closingRequest.caseId}/requests/${closingRequest.id}/close`, "POST", {
                      status: field(f, "status"), reason: field(f, "reason"),
                    });
                    await load(closingRequest.caseId);
                    setClosingRequest(null);
                    setModal("");
                    setNotice("Request closed and link revoked. Reassess the case with this availability update.");
                  });
                }}>
                  <label>Request status
                    <select name="status">
                      <option value="unavailable">Record reported unavailable</option>
                      <option value="withdrawn">Request withdrawn</option>
                    </select>
                  </label>
                  <label>Reason
                    <textarea name="reason" required minLength={3} maxLength={500} rows={4} />
                  </label>
                  <button className="primary" disabled={!!busy}>Close request and revoke link</button>
                </form>
              </>
            )}
            {modal === "evidence" && (
              <>
                <span className="eyebrow">ADD TO THE SOURCE RECORD</span>
                <h2>A new piece of the picture.</h2>
                {me.role === 'member' && <p className="fine">Submitting evidence authorizes Gemini investigation and safe public-reference retrieval automatically, unless you pause it for this case. Original records stay private; fetched sources remain unverified and reviewable. Only submit material you may share and preserve.</p>}
                {me.role === 'member' && <button className="secondary" onClick={()=>setModal('find-evidence')}><Search size={16}/> Find more evidence</button>}
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const f = e.currentTarget;
                    run("Saving evidence", async () => {
                      await api(`/cases/${current!.id}/evidence`, "POST", {
                        title: field(f, "title"),
                        party: field(f, "party"),
                        text: field(f, "text"),
                      });
                      await refresh();
                      setModal("");
                    });
                  }}
                >
                  <label>
                    Source title
                    <input name="title" required maxLength={160} />
                  </label>
                  <label>
                    Supplied by
                    <select name="party" value={evidenceParty} onChange={e => setEvidenceParty(e.target.value)}>
                      {[
                        "buyer",
                        "seller",
                        "carrier",
                        "payment_provider",
                        "other",
                      ].map((p) => (
                        <option key={p} value={p}>
                          {readable(p)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Original content
                    <textarea name="text" rows={6} required maxLength={30000} />
                  </label>
                  <button className="primary" disabled={!!busy}>
                    <Plus size={16} />
                    {me.role==='member' ? 'Add & investigate' : 'Add source'}
                  </button>
                </form>
                <div className="divider">OR UPLOAD A DOCUMENT</div>
                <label className="file-drop">
                  <Upload size={22} />
                  <strong>Select a document</strong>
                  <span>TXT, JSON or text PDF · 5 MB maximum</span>
                  <input
                    type="file"
                    accept=".txt,.json,.pdf"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f)
                        run("Uploading document", async () => {
                          const d = new FormData();
                          d.set("file", f);
                          d.set("party", evidenceParty);
                          await api(`/cases/${current!.id}/upload`, "POST", d);
                          await refresh();
                          setModal("");
                        });
                    }}
                  />
                </label>
                <p className="fine">
                  Evidence is saved before investigation starts. Uploads are reported evidence. No automatic claim of verified
                  origin. Scanned PDFs and images are not yet supported.
                </p>
              </>
            )}
            {modal === "request-review" && reviewedWitness && (
              <>
                <span className="eyebrow">
                  HUMAN REVIEW · EVIDENCE ACQUISITION
                </span>
                <h2>Ask the right source.</h2>
                <p>
                  Check who actually holds this record. Edit the question and
                  intended recipient before creating the restricted invitation.
                </p>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    issueRequest(e.currentTarget);
                  }}
                >
                  <label>
                    Request title
                    <input
                      name="title"
                      defaultValue={reviewedWitness.title}
                      required
                      maxLength={200}
                    />
                  </label>
                  <label>
                    Question
                    <textarea
                      name="question"
                      defaultValue={reviewedWitness.question}
                      required
                      maxLength={1000}
                      rows={5}
                    />
                  </label>
                  <label>
                    Who should supply the evidence?
                    <select
                      name="recipient"
                      defaultValue={reviewedWitness.recipient}
                    >
                      {[
                        "buyer",
                        "seller",
                        "carrier",
                        "payment_provider",
                        "other",
                      ].map((p) => (
                        <option key={p} value={p}>
                          {readable(p)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <p className="fine">
                    The model's suggested recipient may need correction. The
                    invitation does not authenticate a respondent's identity. No
                    message is sent automatically.
                  </p>
                  <button className="primary" disabled={!!busy}>
                    Create reviewed invitation <ArrowRight size={16} />
                  </button>
                </form>
              </>
            )}
            {modal === "request-link" && (
              <>
                <span className="eyebrow">A RESTRICTED INVITATION</span>
                <h2>Ask the next witness.</h2>
                <p>
                  This link allows one response to the requested question. It
                  does not reveal the case file or the other party’s evidence.
                  It expires in seven days.
                </p>
                <div className="copy-link">
                  <input
                    aria-label="Restricted response link"
                    readOnly
                    value={portalLink}
                  />
                  <button
                    onClick={() =>
                      run("Copying link", async () => {
                        await navigator.clipboard.writeText(portalLink);
                        setNotice("Restricted link copied");
                      })
                    }
                  >
                    <Link2 size={18} />
                    Copy
                  </button>
                </div>
                <a
                  className="secondary"
                  href={portalLink}
                  target="_blank"
                  rel="noreferrer"
                >
                  Preview response portal <ExternalLink size={16} />
                </a>
                <p className="fine">
                  No email or notification has been sent. Share with the
                  intended recipient through an appropriate channel. A localhost
                  link works only on this machine; remote recipients require a
                  hosted instance. Keep this link private.
                </p>
              </>
            )}
            {modal === "integrations" && (
              <>
                <span className="eyebrow">TRUTHFUL OPERATIONAL BOUNDARIES</span>
                <h2>Connections & safeguards.</h2>
                <div className="integration-row">
                  <strong>PayPal</strong>
                  <span>
                    {integration
                      ? integration.paypal.status === "verified"
                        ? `Sandbox list verified · ${integration.paypal.disputes} disputes`
                        : integration.paypal.status === "not_configured"
                          ? "Not configured on this host"
                          : `Sandbox connection unavailable · ${integration.paypal.list_status}`
                      : me.role === 'member' ? "Not connected for this workspace" : "Operator connection not accessible in demo"}
                  </span>
                </div>
                <div className="integration-row">
                  <strong>Gemini</strong>
                  <span>{MODEL_NAME(me)} · real calls on demand</span>
                </div>
                <div className="integration-row">
                  <strong>Persistence</strong>
                  <span>
                    {me.role === 'member' ? 'Cloud PostgreSQL · original files, investigations, responses and audit records' : integration?.storage.configured
                      ? `SQLite + private Supabase mirror · ${integration.storage.synced_cases} cases synced · ${integration.storage.pending} pending`
                      : "Private server SQLite · cloud mirror not active in this workspace"}
                  </span>
                </div>
                <div className="integration-row">
                  <strong>Webhooks</strong>
                  <span>
                    {integration?.webhook.configured
                      ? "Configured; delivery verification required"
                      : "Not registered; signature endpoint fails closed"}
                  </span>
                </div>
                {me.role === 'member' && <><div className="integration-row"><strong>Original storage</strong><span>{((me.user.storage_bytes || 0) / 1048576).toFixed(2)} MB / 20 MB</span></div><div className="integration-row"><strong>Today's analysis attempts</strong><span>{me.user.analyses_today || 0} / 10 · resets at 00:00 UTC</span></div></>}
                <div className="integration-row">
                  <strong>Actions</strong>
                  <span>
                    {me.role === 'member' ? 'Merchant actions are not enabled for public accounts' : 'Sandbox only · human review · snapshot binding · durable dispatch reservation'}
                  </span>
                </div>
                <p className="fine">
                  Fictional cases never masquerade as PayPal disputes. The AI
                  has no external action tools. No real-money operations are
                  enabled.
                </p>
                {me.role === "operator" && integration?.paypal.configured && (
                  <form onSubmit={(e) => {
                    e.preventDefault();
                    const id = field(e.currentTarget, "dispute_id");
                    run("Importing PayPal case", async () => {
                      const imported = await api("/paypal/import", "POST", { dispute_id: id });
                      await load();
                      setCurrent(imported);
                      setModal("");
                    });
                  }}>
                    <label>Import an accessible sandbox case by ID
                      <input name="dispute_id" required maxLength={80} pattern="[A-Za-z0-9-]+" placeholder="PayPal case ID" />
                    </label>
                    <button className="secondary" disabled={!!busy}>Retrieve from PayPal</button>
                  </form>
                )}
              </>
            )}
            {modal === "action" && (
              <>
                <span className="eyebrow">PAYPAL SANDBOX · PREPARE ONLY</span>
                <h2>Review a specific response.</h2>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const f = e.currentTarget;
                    run("Preparing action", async () => {
                      setApproval(
                        await api(
                          `/cases/${current!.id}/actions/prepare`,
                          "POST",
                          {
                            action: field(f, "action"),
                            note: field(f, "note"),
                            evidence_type: field(f, "evidence_type") || "PROOF_OF_FULFILLMENT",
                            carrier: field(f, "carrier"),
                            tracking_number: field(f, "tracking_number"),
                          },
                        ),
                      );
                      setModal("approval");
                    });
                  }}
                >
                  <label>
                    Action
                    <select name="action">
                      <option value="send-message">Send message</option>
                      <option value="provide-evidence">
                        Provide evidence
                      </option>
                      <option value="accept-claim">
                        Accept claim (sandbox refund)
                      </option>
                    </select>
                  </label>
                  <label>
                    Evidence type (for evidence submission)
                    <select name="evidence_type">
                      {sellerEvidenceTypes(current).length ? sellerEvidenceTypes(current).map(type => (
                        <option key={type} value={type}>{type === "OTHER" ? "Other evidence notes" : "Actual fulfillment tracking"}</option>
                      )) : <option value="">No supported evidence type requested</option>}
                    </select>
                  </label>
                  <label>
                    Exact message or note
                    <textarea name="note" required maxLength={1200} rows={5} />
                  </label>
                  <label>
                    Carrier (for evidence)
                    <input name="carrier" />
                  </label>
                  <label>
                    Tracking number (for evidence)
                    <input name="tracking_number" />
                  </label>
                  <button className="primary" disabled={!!busy}>
                    Prepare for review <ArrowRight size={16} />
                  </button>
                </form>
              </>
            )}
            {modal === "approval" && approval && (
              <>
                <span className="eyebrow">EXPLICIT ACTION APPROVAL</span>
                <h2>{readable(approval.approval.action)}</h2>
                <p>{approval.warning}</p>
                <pre className="approval-json">
                  {JSON.stringify(approval.approval.payload, null, 2)}
                </pre>
                <p className="mono">Digest: {approval.digest}</p>
                <button
                  className="primary large"
                  disabled={!!busy || !me.sandbox_actions_enabled}
                  onClick={() =>
                    run("Executing approved sandbox action", async () => {
                      const r = await api(
                        `/cases/${current!.id}/actions/execute`,
                        "POST",
                        {
                          approval_id: approval.approval.id,
                          reviewed_digest: approval.digest,
                          confirmed: true,
                        },
                      );
                      setModal("");
                      setNotice(
                        "Sandbox action result: " + r.status + ". " + r.message,
                      );
                      await refresh();
                    })
                  }
                >
                  I approve this exact sandbox action <ShieldCheck size={17} />
                </button>
                {!me.sandbox_actions_enabled && (
                  <p className="fine">
                    Sandbox writes are disabled in server configuration.
                  </p>
                )}
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
function MODEL_NAME(me: any) {
  return me?.model || "Configured Gemini model";
}
function Brand() {
  return (
    <div className="brand">
      <div className="brand-mark">
        V<span />
      </div>
      <strong>
        VERDICT<span>THE MISSING WITNESS</span>
      </strong>
    </div>
  );
}
function Empty({ title, text }: { title: string; text: string }) {
  return (
    <div className="empty">
      <Inbox size={34} />
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
