"""The operator app: FastAPI routes that read a form, call the services, and show the result.

No content rule, approval rule or undo rule lives here. Those are in records.py, repository.py, appstate.py and
history.py, so this layer can be replaced without touching them.
"""

from __future__ import annotations

import datetime as dt
import re
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from site_agent.apply import apply_plan, run_check, state_dir
from site_agent.appstate import AppState
from site_agent.config import Settings, load_settings
from site_agent.drafting import JobRunner, NoticeResult, draft_section, extract_notice, model_status
from site_agent.errors import SiteAgentError
from site_agent.explain import explain_check
from site_agent.factcheck import facts_text, token_in_facts
from site_agent.history import list_runs, undo
from site_agent.launch import launch_report, placeholder_hits, samples
from site_agent.llm import ChatClient, make_client
from site_agent.plan import FileChange, Plan, fingerprint
from site_agent.preflight import run_preflight
from site_agent.records import SPECS, Spec, coerce
from site_agent.reference import read_reference
from site_agent.repository import Outcome, Repository
from site_agent.search import matches, search_values
from site_agent.site import Site

HERE = Path(__file__).parent
CSRF_COOKIE = "sa_csrf"
APPROVAL_STATEMENT = "I have checked these facts against their source."
NAV_GROUPS = (
    ("Content", ("people", "projects", "research", "publications", "facilities")),
    ("Events and news", ("events", "news")),
    ("Opportunities", ("openings",)),
    ("Partners and funding", ("partners", "funding")),
    ("Documents and gallery", ("documents", "gallery")),
)
DRAFT_LENGTH_KEYS = ("body", "summary", "description")


def _safe_next(value: str | None) -> str:
    """Redirect targets must be paths on this site, so a link cannot send the operator somewhere else."""
    if not value or not value.startswith("/") or value.startswith("//") or "\\" in value:
        return "/"
    return value


def _redirect(url: str, msg: str | None = None, err: str | None = None) -> RedirectResponse:
    params = {}
    if msg:
        params["msg"] = msg
    if err:
        params["err"] = err
    if params:
        url = f"{url}{'&' if '?' in url else '?'}{urlencode(params, quote_via=quote)}"
    return RedirectResponse(url, status_code=303)


def state_from_record(spec: Spec, values: dict[str, Any], body: str) -> dict[str, Any]:
    """Turns a record's values into the form's raw state (strings, ticked boxes)."""
    state: dict[str, Any] = {}
    for f in spec.fields:
        value = values.get(f.name)
        if f.kind == "bool":
            state[f.name] = bool(value)
        elif f.kind in ("list", "person_list"):
            state[f.name] = "\n".join(value or [])
        elif isinstance(value, dt.date):
            state[f.name] = value.isoformat()
        elif value is None:
            state[f.name] = ""
        else:
            state[f.name] = str(value)
    state["body"] = body
    return state


def raw_from_form(spec: Spec, form: Any) -> dict[str, Any]:
    raw: dict[str, Any] = {}
    for f in spec.fields:
        raw[f.name] = bool(form.get(f.name)) if f.kind == "bool" else str(form.get(f.name, "") or "")
    raw["body"] = str(form.get("body", "") or "")
    raw["facts"] = str(form.get("facts", "") or "")
    return raw


def create_app(site_root: Path, *, llm: ChatClient | None = None, inline_jobs: bool = False) -> FastAPI:
    settings: Settings = load_settings(site_root)
    site = Site(settings.site)
    repo = Repository(site)
    state = AppState(site)
    jobs = JobRunner(inline=inline_jobs)
    client_holder: dict[str, ChatClient] = {"llm": llm} if llm is not None else {}

    def get_llm() -> ChatClient:
        if "llm" not in client_holder:
            client_holder["llm"] = make_client(settings.llm, log_dir=state_dir(site))
        return client_holder["llm"]

    app = FastAPI(title="CIR website operator", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    templates = Jinja2Templates(directory=HERE / "templates")
    templates.env.globals["NAV_GROUPS"] = NAV_GROUPS
    templates.env.globals["SPECS"] = SPECS

    def page(request: Request, name: str, status: int = 200, **context: Any) -> Response:
        token = request.cookies.get(CSRF_COOKIE)
        context.setdefault("msg", request.query_params.get("msg"))
        context.setdefault("err", request.query_params.get("err"))
        context.update(
            csrf=token or secrets.token_urlsafe(24), settings=state.settings(), current=context.get("current")
        )
        response = templates.TemplateResponse(request, name, context, status_code=status)
        if token is None:
            response.set_cookie(CSRF_COOKIE, context["csrf"], httponly=True, samesite="strict", path="/")
        return response

    async def checked_form(request: Request) -> Any:
        form = await request.form()
        token = request.cookies.get(CSRF_COOKIE)
        if not token or form.get("csrf") != token:
            raise HTTPException(status_code=403, detail="This form has expired. Reload the page and try again.")
        return form

    @app.exception_handler(SiteAgentError)
    async def plain_error(request: Request, exc: SiteAgentError) -> Response:
        # Any refusal from the services becomes one plain sentence on the start screen, never a traceback.
        return _redirect("/", err=str(exc))

    def spec_or_404(key: str) -> Spec:
        if key not in SPECS:
            raise HTTPException(status_code=404, detail="No such collection.")
        return SPECS[key]

    def valid_id(rec_id: str) -> str:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,120}", rec_id):
            raise HTTPException(status_code=404, detail="No such entry.")
        return rec_id

    def form_page(
        request: Request,
        spec: Spec,
        form_state: dict[str, Any],
        *,
        record_id: str | None = None,
        outcome: Outcome | None = None,
        draft: dict[str, Any] | None = None,
        status: int = 200,
    ) -> Response:
        facts_now = facts_text(spec, coerce(spec, form_state)[0], str(form_state.get("facts", "")))
        pending = [t for t in (draft or {}).get("unsupported", []) if not token_in_facts(t, facts_now)]
        dependants = repo.dependants(spec, record_id) if record_id else []
        # A claim is shown while its sentence is still in the text, so editing the sentence clears the warning.
        section_text = " ".join(str(form_state.get((draft or {}).get("section", "")) or "").split())
        claims = [c for c in (draft or {}).get("claims", []) if " ".join(c.split()) in section_text]
        return page(
            request,
            "form.html",
            status,
            current=spec.key,
            spec=spec,
            state=form_state,
            record_id=record_id,
            outcome=outcome,
            errors=outcome.errors if outcome else {},
            blockers=outcome.blockers if outcome else [],
            warnings=outcome.warnings if outcome else [],
            draft=draft,
            draft_pending=pending,
            draft_claims=claims,
            dependants=dependants,
            title=(f"Edit {spec.singular}" if record_id else f"Add {spec.singular}"),
        )

    def handle_save(request: Request, spec: Spec, form: Any, record_id: str | None) -> Response:
        action = str(form.get("action", "preview"))
        raw = raw_from_form(spec, form)
        draft_id = str(form.get("draft_id", "") or "")
        draft = state.load_draft(draft_id) if draft_id else None
        if draft and draft.get("collection") != spec.key:
            draft = None

        if action.startswith("draft:"):
            return start_section_draft(request, spec, action.split(":", 1)[1], raw, record_id)
        if action == "notice":
            return start_notice_draft(request, spec, str(form.get("notice", "")), record_id)
        if action == "reference":
            return start_reference_draft(request, spec, str(form.get("reference", "")), record_id)

        facts = str(raw.get("facts", ""))
        if record_id is None:
            outcome = repo.create(spec, raw, facts)
        else:
            outcome = repo.update(spec, record_id, raw, facts)
        if not outcome.ok:
            return form_page(request, spec, raw, record_id=record_id, outcome=outcome, draft=draft, status=422)
        if outcome.plan is None:
            return form_page(request, spec, raw, record_id=record_id, outcome=outcome, draft=draft)
        return store_preview(spec, outcome, raw, "create" if record_id is None else "update", record_id)

    def store_preview(spec: Spec, outcome: Outcome, raw: dict[str, Any], kind: str, record_id: str | None) -> Response:
        plan = outcome.plan
        assert plan is not None
        rec_id = record_id or plan.changes[0].rel_path.rsplit("/", 1)[-1].removesuffix(".md")
        pid = state.save_preview(
            {
                "kind": kind,
                "collection": spec.key,
                "record_id": rec_id,
                "title": str(outcome.values.get(spec.title_field) or rec_id),
                "summary": plan.summary,
                "changes": outcome.changes,
                "warnings": outcome.warnings,
                "files": [{"rel": c.rel_path, "before": c.before, "after": c.after} for c in plan.changes],
                "fingerprint": fingerprint(plan.changes),
                "raw": raw,
            }
        )
        return _redirect(f"/preview/{pid}")

    def start_section_draft(
        request: Request, spec: Spec, section: str, raw: dict[str, Any], record_id: str | None
    ) -> Response:
        if section == "body" and spec.body_label:
            label, length_key = spec.body_label, "body"
        else:
            try:
                field = spec.field(section)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail="No such section.") from exc
            if field.kind != "long":
                raise HTTPException(status_code=400, detail="That section cannot be drafted.")
            label, length_key = field.label, section if section in DRAFT_LENGTH_KEYS else "summary"
        values = coerce(spec, raw)[0]
        facts = facts_text(spec, values, str(raw.get("facts", "")))
        llm = get_llm()

        def work() -> dict[str, Any]:
            return draft_section(llm, spec, label, length_key, facts)

        def finish(result: dict[str, Any]) -> str:
            return state.save_draft(
                {
                    "kind": "section",
                    "collection": spec.key,
                    "record_id": record_id,
                    "section": section,
                    "text": result["text"],
                    "unsupported": result["unsupported"],
                    "claims": result.get("claims", []),
                }
            )

        job = jobs.start(work, finish)
        return _redirect(f"/jobs/{job}?{urlencode({'next': _back_url(spec, record_id)})}")

    def start_notice_draft(request: Request, spec: Spec, notice: str, record_id: str | None) -> Response:
        if spec.key != "events":
            raise HTTPException(status_code=400, detail="Notices can only be read for events.")
        if not notice.strip():
            return _redirect(_back_url(spec, record_id), err="Paste the notice first, then press Fill from notice.")
        llm = get_llm()
        today = dt.date.today().isoformat()

        def work() -> NoticeResult:
            return extract_notice(llm, notice, today)

        def finish(reading: NoticeResult) -> str:
            return state.save_draft(
                {
                    "kind": "notice",
                    "collection": spec.key,
                    "fields": reading.fields,
                    "notice": notice,
                    "notes": reading.notes,
                }
            )

        job = jobs.start(work, finish)
        return _redirect(f"/jobs/{job}?{urlencode({'next': _back_url(spec, record_id)})}")

    def start_reference_draft(request: Request, spec: Spec, reference: str, record_id: str | None) -> Response:
        if spec.key != "publications":
            raise HTTPException(status_code=400, detail="References can only be read for publications.")
        if not reference.strip():
            return _redirect(
                _back_url(spec, record_id), err="Paste the reference first, then press Fill from reference."
            )
        llm = get_llm()
        this_year = dt.date.today().year

        def work() -> tuple[dict[str, Any], list[str]]:
            return read_reference(llm, reference, this_year)

        def finish(result: tuple[dict[str, Any], list[str]]) -> str:
            fields, notes = result
            return state.save_draft(
                {"kind": "reference", "collection": spec.key, "fields": fields, "reference": reference, "notes": notes}
            )

        job = jobs.start(work, finish)
        return _redirect(f"/jobs/{job}?{urlencode({'next': _back_url(spec, record_id)})}")

    def _back_url(spec: Spec, record_id: str | None) -> str:
        return f"/c/{spec.key}/{record_id}" if record_id else f"/c/{spec.key}/new"

    def _check_and_save() -> dict[str, Any]:
        check_command = settings.site.check_command
        assert check_command
        result = run_check(check_command, site.root)
        saved = {
            "ok": result.ok,
            "output": result.output,
            "command": check_command,
            "time": dt.datetime.now().isoformat(timespec="minutes"),
            "plain": [] if result.ok else explain_check(result.output),
        }
        state.save_check(saved)
        return saved

    # --- start, lists and forms -----------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    def start(request: Request) -> Response:
        report = launch_report(site, repo, state)
        ok, model_message = model_status(settings.llm)
        runs = list_runs(site)[:5]
        return page(
            request,
            "start.html",
            current="start",
            report=report,
            sample_count=len(report.samples),
            last_check=state.last_check(),
            model_ok=ok,
            model_message=model_message,
            runs=runs,
            approvals=state.approvals()[:3],
            title="Start",
        )

    def _search_texts(spec: Spec, item: Any) -> list[str]:
        # An entry that cannot be read is still found by its title, so it can be opened and fixed.
        try:
            return [item.title, *search_values(spec, repo.load(spec, item.id).values)]
        except SiteAgentError:
            return [item.title]

    @app.get("/c/{key}", response_class=HTMLResponse)
    def collection(request: Request, key: str) -> Response:
        spec = spec_or_404(key)
        query = str(request.query_params.get("q", "")).strip()
        only_samples = request.query_params.get("samples") == "1"
        items = repo.listing(spec)
        if query:
            items = [item for item in items if matches(query, _search_texts(spec, item))]
        if only_samples:
            items = [item for item in items if item.sample]
        return page(
            request,
            "list.html",
            current=key,
            spec=spec,
            items=items,
            query=query,
            only_samples=only_samples,
            title=spec.label,
        )

    @app.get("/c/{key}/new", response_class=HTMLResponse)
    def new_form(request: Request, key: str) -> Response:
        spec = spec_or_404(key)
        if not spec.can_add:
            raise HTTPException(status_code=404, detail="This list has a fixed set of entries.")
        draft = state.load_draft(request.query_params.get("draft", "")) if request.query_params.get("draft") else None
        form_state = state_from_record(spec, {f.name: f.default for f in spec.fields}, "")
        if request.query_params.get("from_preview"):
            preview = state.load_preview(request.query_params["from_preview"])
            if preview and preview.get("collection") == key and preview.get("kind") == "create":
                form_state = dict(preview.get("raw", form_state))
        form_state = _apply_draft(spec, form_state, draft)
        return form_page(request, spec, form_state, draft=draft)

    def _apply_draft(spec: Spec, form_state: dict[str, Any], draft: dict[str, Any] | None) -> dict[str, Any]:
        if not draft or draft.get("collection") != spec.key:
            return form_state
        if draft.get("kind") == "notice":
            for name, value in (draft.get("fields") or {}).items():
                if name == "body":
                    form_state["body"] = str(value)
                elif name in form_state:
                    form_state[name] = str(value)
            if draft.get("notice") and not str(form_state.get("facts") or "").strip():
                form_state["facts"] = draft["notice"]  # the notice is the source, so the fact checks can use it
        elif draft.get("kind") == "reference":
            for name, value in (draft.get("fields") or {}).items():
                if name in form_state:
                    form_state[name] = "\n".join(value) if isinstance(value, list) else str(value)
        elif draft.get("kind") == "section":
            form_state[draft["section"]] = draft["text"]
        return form_state

    @app.post("/c/{key}/new")
    async def create(request: Request, key: str) -> Response:
        spec = spec_or_404(key)
        form = await checked_form(request)
        return handle_save(request, spec, form, None)

    @app.get("/c/{key}/{rec_id}", response_class=HTMLResponse)
    def edit_form(request: Request, key: str, rec_id: str) -> Response:
        spec = spec_or_404(key)
        valid_id(rec_id)
        try:
            record = repo.load(spec, rec_id)
        except SiteAgentError as exc:
            return _redirect(f"/c/{key}", err=str(exc))
        form_state = state_from_record(spec, record.values, record.body)
        if request.query_params.get("from_preview"):
            preview = state.load_preview(request.query_params["from_preview"])
            if preview and preview.get("record_id") == rec_id:
                form_state = dict(preview.get("raw", form_state))
        draft = state.load_draft(request.query_params.get("draft", "")) if request.query_params.get("draft") else None
        form_state = _apply_draft(spec, form_state, draft)
        return form_page(request, spec, form_state, record_id=rec_id, draft=draft)

    @app.post("/c/{key}/{rec_id}")
    async def update(request: Request, key: str, rec_id: str) -> Response:
        spec = spec_or_404(key)
        valid_id(rec_id)
        form = await checked_form(request)
        return handle_save(request, spec, form, rec_id)

    @app.post("/c/{key}/{rec_id}/remove")
    async def remove(request: Request, key: str, rec_id: str) -> Response:
        spec = spec_or_404(key)
        valid_id(rec_id)
        await checked_form(request)
        try:
            outcome = repo.archive(spec, rec_id)
        except SiteAgentError as exc:
            return _redirect(f"/c/{key}/{rec_id}", err=str(exc))
        assert outcome.plan is not None
        return store_preview(spec, outcome, {}, "archive", rec_id)

    # --- previews and approval ----------------------------------------------------------------------

    @app.get("/preview/{pid}", response_class=HTMLResponse)
    def preview(request: Request, pid: str) -> Response:
        data = state.load_preview(pid)
        if data is None:
            return _redirect("/", err="That preview has expired. Start the change again.")
        settings_now = state.settings()
        return page(
            request,
            "preview.html",
            current=data["collection"],
            preview=data,
            pid=pid,
            approvers=settings_now["approvers"],
            operator=settings_now["operator_name"],
            statement=APPROVAL_STATEMENT,
            spec=SPECS[data["collection"]],
            title="Review changes",
        )

    @app.post("/preview/{pid}/approve")
    async def approve(request: Request, pid: str) -> Response:
        form = await checked_form(request)
        data = state.load_preview(pid)
        if data is None:
            return _redirect("/", err="That preview has expired. Start the change again.")
        settings_now = state.settings()
        if not settings_now["operator_name"]:
            return _redirect(f"/preview/{pid}", err="Enter your name in Settings before you approve.")
        approver = next((a for a in settings_now["approvers"] if a["name"] == form.get("approver")), None)
        if approver is None:
            return _redirect(f"/preview/{pid}", err="Choose an approver from the list. The list is kept in Settings.")
        if not form.get("statement"):
            return _redirect(f"/preview/{pid}", err="Tick the statement to approve.")
        unticked = [w for i, w in enumerate(data["warnings"]) if not form.get(f"warn_{i}")]
        if unticked:
            return _redirect(f"/preview/{pid}", err="Tick each warning to say you have checked it.")

        changes = [FileChange(f["rel"], f["before"], f["after"]) for f in data["files"]]
        if fingerprint(changes) != data["fingerprint"]:
            return _redirect(f"/preview/{pid}", err="The text no longer matches what was previewed. Start again.")
        plan = _plan_from(data, changes)
        if settings.site.check_command:
            # Off the event loop, because a real site check can take minutes.
            preflight = await run_in_threadpool(run_preflight, site, plan, settings.site.check_command, state_dir(site))
            if preflight.status == "failed":
                state.save_check(
                    {
                        "ok": False,
                        "output": preflight.output,
                        "command": settings.site.check_command,
                        "time": dt.datetime.now().isoformat(timespec="minutes"),
                        "stage": "preflight",
                    }
                )
                return _redirect(
                    f"/preview/{pid}",
                    err="The site check failed on a copy with these changes, so nothing was written. "
                    "The details are on the Check screen.",
                )
        approval_id = secrets.token_hex(5)
        try:
            result = apply_plan(
                site, plan, command=f"web:{data['kind']}", model=settings.llm.model, approval_id=approval_id
            )
        except SiteAgentError as exc:
            return _redirect(f"/preview/{pid}", err=str(exc))
        state.add_approval(
            {
                "id": approval_id,
                "kind": "content",
                "preview_id": pid,
                "run_id": result.run_id,
                "summary": data["summary"],
                "files": [c.rel_path for c in changes],
                "changes": data["changes"],
                "warnings_ticked": data["warnings"],
                "fingerprint": data["fingerprint"],
                "approver": approver["name"],
                "approver_role": approver.get("role", ""),
                "recorded_by": settings_now["operator_name"],
                "statement": APPROVAL_STATEMENT,
            }
        )
        state.delete_preview(pid)
        if settings.site.check_command:
            job = jobs.start(_check_and_save)
            return _redirect(f"/jobs/{job}?{urlencode({'next': '/check'})}")
        return _redirect("/history", msg=f"Saved. Undo is available below (run {result.run_id}).")

    def _plan_from(data: dict[str, Any], changes: list[FileChange]) -> Plan:
        return Plan(summary=data["summary"], changes=changes)

    @app.post("/preview/{pid}/discard")
    async def discard(request: Request, pid: str) -> Response:
        await checked_form(request)
        data = state.load_preview(pid)
        state.delete_preview(pid)
        if data is None:
            return _redirect("/")
        back = (
            f"/c/{data['collection']}/{data['record_id']}"
            if data["kind"] != "create"
            else f"/c/{data['collection']}/new"
        )
        return _redirect(back, msg="The changes were discarded. Nothing was saved.")

    # --- drafting jobs ----------------------------------------------------------------------------------

    @app.get("/jobs/{job_id}", response_class=HTMLResponse)
    def job(request: Request, job_id: str) -> Response:
        next_url = _safe_next(request.query_params.get("next"))
        status = jobs.status(job_id)
        if status is None:
            return _redirect(next_url, err="That work is no longer known. The app may have restarted. Start it again.")
        if status["state"] == "running":
            return page(
                request,
                "wait.html",
                next=next_url,
                job_id=job_id,
                seconds=status["seconds"],
                characters=status["characters"],
                title="Working",
            )
        if status["state"] == "done":
            result = status["result"]
            if isinstance(result, str) and result and result.isalnum():
                separator = "&" if "?" in next_url else "?"
                return RedirectResponse(f"{next_url}{separator}draft={result}", status_code=303)
            return RedirectResponse(next_url, status_code=303)
        message = status["error"] or "The work was stopped before it finished."
        return page(request, "wait.html", next=next_url, job_id=job_id, failed=message, title="Stopped")

    @app.post("/jobs/{job_id}/cancel")
    async def cancel_job(request: Request, job_id: str) -> Response:
        form = await checked_form(request)
        jobs.cancel(job_id)
        return _redirect(f"/jobs/{job_id}?{urlencode({'next': _safe_next(str(form.get('next', '/')))})}")

    # --- history ----------------------------------------------------------------------------------------

    @app.get("/history", response_class=HTMLResponse)
    def history(request: Request) -> Response:
        return page(
            request,
            "history.html",
            current="history",
            runs=list_runs(site),
            approvals=state.approvals(),
            title="History",
        )

    @app.post("/history/{run_id}/undo")
    async def undo_run(request: Request, run_id: str) -> Response:
        await checked_form(request)
        try:
            actions = undo(site, run_id)
        except SiteAgentError as exc:
            return _redirect("/history", err=str(exc))
        names = ", ".join(path for _, path in actions)
        return _redirect("/history", msg=f"Undone: {names}. Run the site check again before launch.")

    # --- checks, launch and samples -----------------------------------------------------------------

    @app.get("/check", response_class=HTMLResponse)
    def check(request: Request) -> Response:
        last = state.last_check()
        if last and not last.get("ok") and "plain" not in last:
            # A result saved before the plain sentences existed still gets them.
            last = {**last, "plain": explain_check(str(last.get("output", "")))}
        return page(
            request,
            "check.html",
            current="check",
            last=last,
            command=settings.site.check_command,
            title="Check the site",
        )

    @app.post("/check/run")
    async def run_site_check(request: Request) -> Response:
        await checked_form(request)
        if not settings.site.check_command:
            return _redirect(
                "/check", err="No check command is set. The technical contact sets check_command in site-agent.toml."
            )
        job_id = jobs.start(_check_and_save)
        return _redirect(f"/jobs/{job_id}?{urlencode({'next': '/check'})}")

    @app.get("/launch", response_class=HTMLResponse)
    def launch(request: Request) -> Response:
        return page(request, "launch.html", current="launch", report=launch_report(site, repo, state), title="Launch")

    @app.get("/samples", response_class=HTMLResponse)
    def sample_list(request: Request) -> Response:
        content = [rel for rel in site.iter_text_files() if rel.startswith(site.content_dir + "/")]
        hits = placeholder_hits(site, content)[:300]
        return page(
            request,
            "samples.html",
            current="samples",
            items=samples(repo),
            hits=hits,
            title="Samples and placeholders",
        )

    # --- settings ---------------------------------------------------------------------------------------

    @app.get("/settings", response_class=HTMLResponse)
    def settings_page(request: Request) -> Response:
        ok, message = model_status(settings.llm)
        return page(
            request,
            "settings.html",
            current="settings",
            approver_lines="\n".join(f"{a['name']} | {a.get('role', '')}" for a in state.settings()["approvers"]),
            model_ok=ok,
            model_message=message,
            llm=settings.llm,
            site_root=str(site.root),
            title="Settings",
        )

    @app.post("/settings")
    async def save_settings(request: Request) -> Response:
        form = await checked_form(request)
        approvers = []
        for line in str(form.get("approvers", "")).splitlines():
            if not line.strip():
                continue
            name, _, role = line.partition("|")
            if name.strip():
                approvers.append({"name": name.strip(), "role": role.strip()})
        state.save_settings(str(form.get("operator_name", "")).strip(), approvers)
        return _redirect("/settings", msg="Settings saved.")

    # --- a small JSON view, for a future front end ----------------------------------------------------

    @app.get("/api/launch")
    def api_launch() -> JSONResponse:
        report = launch_report(site, repo, state)
        return JSONResponse(
            {"ready": report.ready, "blockers": report.blockers, "warnings": report.warnings, "passes": report.passes}
        )

    @app.get("/api/{key}")
    def api_list(key: str) -> JSONResponse:
        spec = spec_or_404(key)
        return JSONResponse(
            [{"id": i.id, "title": i.title, "sample": i.sample, "problems": i.problems} for i in repo.listing(spec)]
        )

    return app


__all__ = ["create_app", "state_from_record", "raw_from_form", "APPROVAL_STATEMENT"]
