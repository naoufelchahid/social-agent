import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type Candidate = { candidate_id: string; title: string; status: string; score: number; angle: string; canonical_url: string };
type Post = { post_id: string; stage: string; url: string; last_error: string | null };
type Snapshot = {
  active_post_id: string | null;
  candidates: Candidate[];
  posts: Post[];
  research: { sources: string | null; latest_report: string | null };
  oauth: { x_configured: boolean; linkedin_configured: boolean };
  command: { action: string; status: string; message: string | null } | null;
};
type Route = "Candidates" | "Intake" | "Pipeline" | "Review" | "Outcomes";
const routes: Route[] = ["Candidates", "Intake", "Pipeline", "Review", "Outcomes"];

async function command(payload: Record<string, string>): Promise<void> {
  const response = await fetch("/api/v1/commands", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  if (!response.ok) throw new Error((await response.json()).message ?? "Command failed");
}

function App() {
  const [route, setRoute] = useState<Route>("Candidates");
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const load = async () => {
    try { const response = await fetch("/api/v1/snapshot"); if (!response.ok) throw new Error("Snapshot unavailable"); setSnapshot(await response.json()); setError(null); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Snapshot unavailable"); }
  };
  useEffect(() => { void load(); const timer = window.setInterval(() => { if (snapshot?.command?.status === "running") void load(); }, 2500); return () => window.clearInterval(timer); }, [snapshot?.command?.status]);
  const submit = async (payload: Record<string, string>) => { try { await command(payload); setNotice("Command submitted"); await load(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Command failed"); } };
  return <div className="shell"><aside><h1>Social Agent</h1><nav aria-label="Workspace pages">{routes.map((item) => <button key={item} className={route === item ? "selected" : ""} onClick={() => setRoute(item)}>{item}</button>)}</nav></aside><main><header><p>Local operator console</p>{snapshot?.command && <p className="command">{snapshot.command.action}: {snapshot.command.status} {snapshot.command.message ?? ""}</p>}</header>{notice && <p role="status">{notice}</p>}{error && <p role="alert">{error}</p>}{!snapshot ? <p>Loading workspace…</p> : <Page route={route} snapshot={snapshot} submit={submit} />}</main></div>;
}

function Page({ route, snapshot, submit }: { route: Route; snapshot: Snapshot; submit: (value: Record<string, string>) => Promise<void> }) {
  if (route === "Candidates") return <section><h2>Candidates</h2>{snapshot.candidates.length ? snapshot.candidates.map((candidate) => <article key={candidate.candidate_id}><h3>{candidate.title}</h3><p>{candidate.status} · {candidate.score}/10</p><p>{candidate.angle}</p><p>{candidate.canonical_url}</p>{candidate.status === "active" && <p><button onClick={() => void submit({ action: "promote_candidate", candidate_id: candidate.candidate_id })}>Promote</button><button onClick={() => { if (window.confirm(`Delete ${candidate.title}? This cannot be undone.`) && window.confirm(`Permanently delete ${candidate.canonical_url}?`)) void submit({ action: "delete_candidate", candidate_id: candidate.candidate_id }); }}>Delete permanently</button></p>}</article>) : <p>No retained candidates.</p>}</section>;
  if (route === "Intake") return <section><h2>Intake</h2><button onClick={() => void submit({ action: "research_intake" })}>Run intake</button><h3>Latest report</h3><pre>{snapshot.research.latest_report ?? "No intake report."}</pre></section>;
  if (route === "Pipeline") return <section><h2>Pipeline</h2><p>Active post: {snapshot.active_post_id ?? "None"}</p><button onClick={() => void submit({ action: "run" })}>Run default queue</button><button onClick={() => void submit({ action: "resume" })}>Resume</button>{snapshot.posts.map((post) => <article key={post.post_id}><h3>{post.post_id} · {post.stage}</h3><p>{post.url}</p><p>{post.last_error}</p>{post.stage === "failed" && <button onClick={() => void submit({ action: "retry_failed", post_id: post.post_id })}>Retry</button>}</article>)}</section>;
  if (route === "Review") return <section><h2>Review</h2>{snapshot.posts.filter((post) => post.stage === "human_review").map((post) => <article key={post.post_id}><h3>{post.post_id}</h3><p>Use the CLI review command for the complete local evidence and explicit decision flow.</p></article>)}<p>Reviewable packages appear here when ready.</p></section>;
  return <section><h2>Outcomes</h2><p>X OAuth: {snapshot.oauth.x_configured ? "configured" : "not configured"}</p><p>LinkedIn OAuth: {snapshot.oauth.linkedin_configured ? "configured" : "not configured"}</p><button onClick={() => void submit({ action: "connect", platform: "x" })}>Connect X</button><button onClick={() => void submit({ action: "connect", platform: "linkedin" })}>Connect LinkedIn</button><button onClick={() => void submit({ action: "connect", platform: "all" })}>Connect both</button></section>;
}

createRoot(document.getElementById("root")!).render(<App />);
