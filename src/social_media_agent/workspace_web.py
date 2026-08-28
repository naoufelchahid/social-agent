"""Loopback HTTP presentation for the local operator workspace."""
# ruff: noqa: E501

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from social_media_agent.operator_workspace import OperatorWorkspace


def build_workspace_server(
    workspace: OperatorWorkspace, port: int = 0
) -> ThreadingHTTPServer:
    """Create a local-only server; callers must serve it on loopback."""
    handler = _handler_for(workspace)
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def serve_workspace(workspace: OperatorWorkspace, port: int = 8767) -> None:
    """Serve the local browser workspace until the operator stops the process."""
    server = build_workspace_server(workspace, port)
    with server:
        server.serve_forever()


def _handler_for(workspace: OperatorWorkspace) -> type[BaseHTTPRequestHandler]:
    class WorkspaceHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._bytes(HTTPStatus.OK, _PAGE.encode(), "text/html; charset=utf-8")
                return
            if parsed.path == "/api/snapshot":
                query = parse_qs(parsed.query)
                try:
                    snapshot = workspace.snapshot(
                        candidate_status=query.get("candidate_status", [None])[0]
                    )
                except ValueError as exc:
                    self._json(
                        HTTPStatus.BAD_REQUEST, {"ok": False, "message": str(exc)}
                    )
                    return
                self._json(HTTPStatus.OK, snapshot)
                return
            parts = parsed.path.split("/")
            if (
                len(parts) == 5
                and parts[:3] == ["", "api", "posts"]
                and parts[4] == "image"
            ):
                try:
                    image = workspace.image_path(parts[3])
                    self._bytes(HTTPStatus.OK, image.read_bytes(), "image/png")
                except (OSError, ValueError):
                    self._json(
                        HTTPStatus.NOT_FOUND,
                        {"ok": False, "message": "Image unavailable"},
                    )
                return
            self._json(HTTPStatus.NOT_FOUND, {"ok": False, "message": "Not found"})

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/api/commands":
                self._json(HTTPStatus.NOT_FOUND, {"ok": False, "message": "Not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 14 * 1024 * 1024:
                    raise ValueError("Command body exceeds the local upload limit")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("Command body must be a JSON object")
                result = workspace.submit(payload)
            except (ValueError, json.JSONDecodeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "message": str(exc)})
                return
            self._json(
                HTTPStatus.OK if result["ok"] else HTTPStatus.BAD_REQUEST, result
            )

        def _json(self, status: HTTPStatus, value: object) -> None:
            self._bytes(
                status,
                json.dumps(value, ensure_ascii=False).encode(),
                "application/json; charset=utf-8",
            )

        def _bytes(
            self, status: HTTPStatus, contents: bytes, content_type: str
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(contents)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; style-src 'self' 'unsafe-inline'",
            )
            self.end_headers()
            self.wfile.write(contents)

        def log_message(self, format: str, *args: object) -> None:
            return

    return WorkspaceHandler


_PAGE = """<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Social Agent · Local workspace</title>
<style>
body{font:16px system-ui,sans-serif;max-width:1120px;margin:auto;padding:2rem;background:#f5f7f8;color:#172027}header{display:flex;justify-content:space-between;align-items:center;gap:1rem}section{background:white;border:1px solid #d7dde1;border-radius:.7rem;padding:1rem;margin:1rem 0}button,select{font:inherit;padding:.5rem .7rem}button:focus,select:focus{outline:3px solid #0b70b7;outline-offset:2px}.muted{color:#596670}.danger{background:#8d1b1b;color:white}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1rem}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f6f7;padding:.8rem}.status{font-weight:600}dialog{max-width:38rem}img{max-width:100%;height:auto}@media(max-width:600px){body{padding:1rem}}
</style>
<body><header><div><h1>Local operator workspace</h1><p class="muted">Loopback only · one operator · no scheduling or remote administration</p></div><button onclick="load()">Refresh</button></header>
<p id="notice" class="status" aria-live="polite"></p><section><h2>Pipeline</h2><p id="pipeline"></p><button data-action="run">Run queue</button> <button data-action="resume">Resume</button> <button data-action="retry_failed">Retry all failed</button></section>
<div class="grid"><section><h2>Posts</h2><div id="posts"></div></section><section><h2>Candidate portfolio</h2><label>Status <select id="filter" onchange="load()"><option value="">All</option><option>active</option><option>promoted</option><option>expired</option></select></label><div id="candidates"></div></section></div>
<div class="grid"><section><h2>Research intake</h2><p class="muted">Read-only discovery; it never drafts or publishes.</p><button data-action="research_intake">Run intake</button><h3>Latest report</h3><pre id="report"></pre><h3>Source configuration</h3><pre id="sources"></pre></section><section><h2>OAuth</h2><p id="oauth"></p><button onclick="command({action:'connect',platform:'all'})">Connect local accounts</button><p class="muted">Tokens, authorization codes, and secrets are never shown here.</p></section></div>
<dialog id="confirm"><form method="dialog"><h2>Confirm acceptance</h2><p>Acceptance creates an immutable approved draft and immediately starts X then LinkedIn publication to your personal accounts.</p><button value="cancel">Cancel</button><button id="accept" value="accept" class="danger">Accept and publish</button></form></dialog>
<script>
let snap={}; const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function load(){let f=document.querySelector('#filter').value;let r=await fetch('/api/snapshot'+(f?'?candidate_status='+encodeURIComponent(f):''));snap=await r.json();document.querySelector('#pipeline').textContent=`${snap.active_post_id?'Active: '+snap.active_post_id:'No active post'} · ${Object.entries(snap.counts).map(([k,v])=>k+': '+v).join(', ')||'No posts'}`;document.querySelector('#notice').textContent=snap.command?`${snap.command.action}: ${snap.command.status}${snap.command.message?' — '+snap.command.message:''}`:'';document.querySelector('#posts').innerHTML=snap.posts.map(p=>`<article><h3>${escape(p.post_id)} <small>${escape(p.stage)}</small></h3><p>${escape(p.url)}</p>${p.last_error?'<p class="danger">'+escape(p.last_error)+'</p>':''}${p.review?review(p):''}${p.publication?'<pre>'+escape(JSON.stringify(p.publication,null,2))+'</pre>':''}</article>`).join('')||'<p class="muted">No persisted posts.</p>';document.querySelector('#candidates').innerHTML=snap.candidates.map(c=>`<article><h3>${escape(c.title)}</h3><p>${escape(c.status)} · ${escape(c.score)}/10 · ${escape(c.source_family)}</p><p>${escape(c.angle)}</p><p>${escape(c.professional_use_case)}</p><button onclick="command({action:'promote_candidate',candidate_id:'${escape(c.candidate_id)}'})" ${c.status==='active'?'':'disabled'}>Promote</button></article>`).join('')||'<p class="muted">No candidates.</p>';document.querySelector('#report').textContent=snap.research.latest_report||'No intake report.';document.querySelector('#sources').textContent=snap.research.sources||'No configured sources.';document.querySelector('#oauth').textContent=`X ${snap.oauth.x_configured?'configured':'not configured'} · LinkedIn ${snap.oauth.linkedin_configured?'configured':'not configured'}`}
function review(p){let b=`<details><summary>Human review package</summary><pre>${escape(JSON.stringify(p.review,null,2))}</pre>${p.review.image_url?'<img alt="Generated review image" src="'+p.review.image_url+'">':''}<button onclick="reviewAction('${escape(p.post_id)}','regenerate_text')">Regenerate text</button> <button onclick="reviewAction('${escape(p.post_id)}','regenerate_image')">Regenerate image</button> <label>Replace image <input type="file" accept="image/png" onchange="replaceImage('${escape(p.post_id)}',this.files[0])"></label><button onclick="reviewAction('${escape(p.post_id)}','save_quit')">Save and quit</button> <button onclick="reviewAction('${escape(p.post_id)}','skip')">Skip</button> <button onclick="reviewAction('${escape(p.post_id)}','reject')">Reject</button> <button onclick="confirmAccept('${escape(p.post_id)}')">Accept</button></details>`;return b}
async function command(body){let r=await fetch('/api/commands',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});let v=await r.json();document.querySelector('#notice').textContent=v.message;load()};function reviewAction(id,a){let feedback=(a==='regenerate_text'||a==='regenerate_image')?prompt('Feedback:'):null;if((a==='regenerate_text'||a==='regenerate_image')&&!feedback)return;command({action:'review',post_id:id,review_action:a,feedback})};function replaceImage(id,file){if(!file)return;let reader=new FileReader();reader.onload=()=>command({action:'review',post_id:id,review_action:'replace_image',replacement_image_base64:reader.result.split(',',2)[1]});reader.readAsDataURL(file)};function confirmAccept(id){let d=document.querySelector('#confirm');d.showModal();document.querySelector('#accept').onclick=()=>command({action:'review',post_id:id,review_action:'accept'})};document.querySelectorAll('[data-action]').forEach(b=>b.onclick=()=>command({action:b.dataset.action}));load();setInterval(load,3000);
</script></body></html>"""
