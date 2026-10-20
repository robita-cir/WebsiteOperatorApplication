"""Command-line entry point: `site-agent <command>`.

Commands that change files only preview by default. Add --apply to write the changes, and --yes to skip the question.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from site_agent import __version__
from site_agent.apply import apply_plan, restore_run, run_check, state_dir
from site_agent.config import Settings, load_settings
from site_agent.errors import SiteAgentError
from site_agent.llm import ChatClient, LLMError, make_client
from site_agent.plan import Plan
from site_agent.preflight import run_preflight
from site_agent.schemas import COLLECTIONS
from site_agent.site import Site
from site_agent.text_utils import MIN_NEEDLE
from site_agent.validate import check_collection, check_plan, sample_files
from site_agent.workflows import plan_add_event, plan_update_event


def _settings_and_site(args: argparse.Namespace) -> tuple[Settings, Site]:
    settings = load_settings(args.site, model=getattr(args, "model", None))
    return settings, Site(settings.site)


def _read_input(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    path = Path(source)
    if not path.is_file():
        raise SiteAgentError(f"input file not found: {path}")
    return path.read_text(encoding="utf-8-sig")


def _confirm(question: str) -> bool:
    if not sys.stdin.isatty():
        raise SiteAgentError("cannot ask for confirmation without a terminal. Add --yes to apply without asking.")
    return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")


def _llm(settings: Settings, client: ChatClient | None) -> ChatClient:
    return client if client is not None else make_client(settings.llm)


def _review_and_apply(site: Site, settings: Settings, plan: Plan, args: argparse.Namespace, command: str) -> int:
    print(plan.render())
    if not plan.changes:
        return 0
    problems = check_plan(site, plan)
    if problems:
        print("\nNot written. Fix these first:")
        for issue in problems:
            print(f"  {issue.rel_path}: {issue.message}")
        return 1
    # A model edit that could not be placed safely is never half applied: the whole update waits for a person.
    if plan.failures:
        print(
            "\nNot written. The model's edits could not all be placed safely. Edit those lines by hand, then try again:"
        )
        for failure in plan.failures:
            print(f"  {failure}")
        return 1
    if not args.apply:
        print("\nDry run: nothing was written. Run again with --apply to write these changes.")
        return 0
    if settings.site.check_command:
        preflight = run_preflight(site, plan, settings.site.check_command, state_dir(site))
        if preflight.status == "failed":
            print("\nNot written. The site check failed on a copy with these changes.")
            print(preflight.output)
            return 1
        if preflight.status == "skipped":
            print(f"\n{preflight.reason}")
    if not args.yes and not _confirm(f"Write {len(plan.changes)} file(s) now?"):
        print("Cancelled. Nothing was written.")
        return 1

    result = apply_plan(site, plan, command=command, model=settings.llm.model)
    print(f"\nWritten. Run id: {result.run_id}")
    print(f"  Backups of replaced files: {result.backup_dir}")
    print(f"  To undo this run: site-agent restore {result.run_id} --site {site.root}")

    if settings.site.check_command:
        print(f"\nChecking the site with: {settings.site.check_command}")
        check = run_check(settings.site.check_command, site.root)
        if check.ok:
            print("Check passed.")
            return 0
        print(check.output)
        print(f"\nThe check failed. The changes are still written. To undo them: site-agent restore {result.run_id}")
        return 1
    return 0


def cmd_scan(args: argparse.Namespace, client: ChatClient | None) -> int:
    settings, site = _settings_and_site(args)
    print(f"Site:  {site.root}")
    print(f"Model: {settings.llm.model} via {settings.llm.provider} at {settings.llm.base_url}")
    collections = site.collections_present()
    if not collections:
        print(f"No collections found in {site.content_dir}/.")
        return 1
    for name in collections:
        status = "validated" if name in COLLECTIONS else "not supported yet"
        print(f"  {name:<14} {len(site.collection_files(name)):>4} file(s)   ({status})")
    for name in COLLECTIONS:
        samples = sample_files(site, name)
        if samples:
            print(f"Sample entries still marked for replacement in {name}: {len(samples)}")
    return 0


def cmd_validate(args: argparse.Namespace, client: ChatClient | None) -> int:
    _, site = _settings_and_site(args)
    errors, warnings = [], []
    for name in COLLECTIONS:
        file_errors, file_warnings = check_collection(site, name)
        errors += file_errors
        warnings += file_warnings
    for issue in errors:
        print(f"error   {issue.rel_path}: {issue.message}")
    for issue in warnings:
        print(f"warning {issue.rel_path}: {issue.message}")
    checked = sum(len(site.collection_files(name)) for name in COLLECTIONS)
    print(f"{checked} file(s) checked: {len(errors)} error(s), {len(warnings)} warning(s).")
    return 1 if errors else 0


def cmd_find(args: argparse.Namespace, client: ChatClient | None) -> int:
    _, site = _settings_and_site(args)
    if len(args.text.strip()) < MIN_NEEDLE:
        raise SiteAgentError(f"search text must be at least {MIN_NEEDLE} characters")
    mentions = site.find_mentions([args.text])
    for mention in mentions:
        print(f"{mention.rel_path}:{mention.line_no}: {mention.line}")
    print(f"{len(mentions)} mention(s) found.")
    return 0


def cmd_add_event(args: argparse.Namespace, client: ChatClient | None) -> int:
    settings, site = _settings_and_site(args)
    text = _read_input(args.source)
    plan = plan_add_event(site, _llm(settings, client), text, slug=args.slug)
    return _review_and_apply(site, settings, plan, args, command="add-event")


def cmd_update_event(args: argparse.Namespace, client: ChatClient | None) -> int:
    settings, site = _settings_and_site(args)
    instruction = args.instruction if args.instruction is not None else _read_input(args.source)
    if not instruction.strip():
        raise SiteAgentError("the instruction is empty")
    plan = plan_update_event(site, _llm(settings, client), args.query, instruction, assisted=args.assisted)
    return _review_and_apply(site, settings, plan, args, command="update-event")


def cmd_restore(args: argparse.Namespace, client: ChatClient | None) -> int:
    _, site = _settings_and_site(args)
    actions = restore_run(site, args.run_id)
    for action, rel in actions:
        print(f"{action} {rel}")
    print(f"Run {args.run_id} undone ({len(actions)} file(s)).")
    return 0


def _add_common(parser: argparse.ArgumentParser, *, writes: bool) -> None:
    parser.add_argument("--site", type=Path, default=Path("."), help="folder of the website (default: current folder)")
    if writes:
        parser.add_argument("--model", help="model name, overriding site-agent.toml")
        parser.add_argument(
            "--apply", action="store_true", help="write the changes (without this, only a preview is shown)"
        )
        parser.add_argument("--yes", action="store_true", help="do not ask for confirmation before writing")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="site-agent", description="Make content changes to a static website with a local model."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    scan = commands.add_parser("scan", help="show the collections in the site and the model settings")
    _add_common(scan, writes=False)
    scan.set_defaults(handler=cmd_scan)

    validate = commands.add_parser(
        "validate", help="check every validated content file against its schema (no model needed)"
    )
    _add_common(validate, writes=False)
    validate.set_defaults(handler=cmd_validate)

    find = commands.add_parser("find", help="list every line in the site that mentions some text (no model needed)")
    find.add_argument("text", help="text to search for, at least 3 characters")
    _add_common(find, writes=False)
    find.set_defaults(handler=cmd_find)

    add = commands.add_parser("add-event", help="add an event from a short notice")
    add.add_argument(
        "--from",
        dest="source",
        required=True,
        metavar="FILE",
        help="file with the notice, or - to type it at the keyboard",
    )
    add.add_argument("--slug", help="file name for the event, for example robot-learning-day")
    _add_common(add, writes=True)
    add.set_defaults(handler=cmd_add_event)

    update = commands.add_parser("update-event", help="change an event and the places that mention it")
    update.add_argument("query", help="the event's file name or exact title")
    group = update.add_mutually_exclusive_group(required=True)
    group.add_argument("--instruction", help="what changed, in one or more sentences")
    group.add_argument(
        "--from", dest="source", metavar="FILE", help="file with the instruction, or - for keyboard input"
    )
    update.add_argument(
        "--assisted",
        action="store_true",
        help="let the model propose edits to lines that show the old details without naming the event (check them)",
    )
    _add_common(update, writes=True)
    update.set_defaults(handler=cmd_update_event)

    restore = commands.add_parser("restore", help="undo a run that was written with --apply")
    restore.add_argument("run_id", help="run id printed when the changes were written")
    _add_common(restore, writes=False)
    restore.set_defaults(handler=cmd_restore)
    return parser


def _use_utf8_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv: list[str] | None = None, *, client: ChatClient | None = None) -> int:
    """Runs one command and returns its exit code. `client` lets tests supply a model without a server."""
    _use_utf8_output()
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args, client)
    except SiteAgentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except LLMError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print("See docs/MODELS.md for how to start the model server.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStopped. Nothing further was written.", file=sys.stderr)
        return 130
