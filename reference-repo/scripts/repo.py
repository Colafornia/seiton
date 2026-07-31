#!/usr/bin/env python3
"""reference-repo: persistent, ref-isolated shallow clones under ~/.agent-context.

Borrows:
  lburgazzoli/agents -> clone dir isolated by ref:  repos/<owner>/<repo>@<ref>/
  FluxCD             -> each source reconciled independently, lock aggregates
  Repomix            -> commit pin + per-repo include/ignore filters
  GitMCP             -> on-demand retrieval (the agent greps/reads, never bulk-loads)

Layout:
  ~/.agent-context/repos.yaml   registry (owner/repo -> url, ref, include, ignore)
  ~/.agent-context/lock.yaml    per-task commit pin (aggregate of pinned sources)
  ~/.agent-context/repos/<owner>/<repo>@<ref>/   shallow clone
"""
import argparse, os, re, subprocess, sys
from pathlib import Path

BASE = Path(os.environ.get("REFERENCE_REPOS_DIR", os.path.expanduser("~/.agent-context")))
REPOS_YAML = BASE / "repos.yaml"
LOCK_YAML = BASE / "lock.yaml"
REPOS_DIR = BASE / "repos"

try:
    import yaml
except ImportError:
    sys.exit("reference-repo: pyyaml required (pip install pyyaml)")


def die(msg, code=1):
    print(f"reference-repo: {msg}", file=sys.stderr); sys.exit(code)

def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)

def git_ok(args, **kw):
    r = run(["git", *args], **kw)
    if r.returncode != 0:
        die(f"git failed: {' '.join(args)}\n{r.stderr.strip()}")
    return r

def key_to_parts(key):
    """owner/repo -> (owner, repo). ref is read from registry, not the key."""
    if "/" not in key or key.count("/") > 1:
        die(f"invalid source key (want owner/repo): {key}")
    owner, repo = key.split("/", 1)
    return owner, repo

def clone_dir(key, ref):
    owner, repo = key_to_parts(key)
    return REPOS_DIR / owner / f"{repo}@{ref}"

def source_id(key, ref):
    return f"{key}@{ref}"

# ---- registry (repos.yaml) ----
def load_registry():
    if not REPOS_YAML.exists():
        return {"repos": {}}
    d = yaml.safe_load(REPOS_YAML.read_text()) or {}
    d.setdefault("repos", {})
    return d

def save_registry(d):
    BASE.mkdir(parents=True, exist_ok=True)
    REPOS_YAML.write_text(yaml.safe_dump(d, sort_keys=True, allow_unicode=True))

# ---- lock (lock.yaml) ----
def load_lock():
    if not LOCK_YAML.exists():
        return {"pinned": {}}
    d = yaml.safe_load(LOCK_YAML.read_text()) or {}
    d.setdefault("pinned", {})
    return d

def save_lock(d):
    BASE.mkdir(parents=True, exist_ok=True)
    LOCK_YAML.write_text(yaml.safe_dump(d, sort_keys=True, allow_unicode=True))

# ---- ref resolution (latest -> newest non-prerelease tag) ----
PRE_RE = re.compile(r"-\d*.*(rc|alpha|beta|pre|dev|snapshot)", re.I)
def resolve_ref(url, ref):
    """Return (ref_to_fetch, resolved_label). 'latest' -> newest stable tag."""
    if ref != "latest":
        return ref, ref
    r = run(["git", "ls-remote", "--tags", "--sort=-v:refname", url])
    if r.returncode != 0:
        die(f"cannot list tags for {url}: {r.stderr.strip()}")
    for line in r.stdout.splitlines():
        # <sha>\trefs/tags/<tag>  ; ignore peeled refs/tags/<tag>^{}
        m = re.match(r"[0-9a-f]+\trefs/tags/(.+)$", line)
        if not m or m.group(1).endswith("^{}"):
            continue
        tag = m.group(1)
        if PRE_RE.search(tag):
            continue
        return tag, tag
    die(f"no stable tags found for {url}; set an explicit ref")

# ---- per-source reconcile (FluxCD: independent) ----
def reconcile(key, spec, force=False):
    """Reconcile one source independently (FluxCD). Returns (ok, detail)."""
    url = spec.get("url")
    ref = spec.get("ref") or "main"
    if not url:
        return False, f"{key}: missing url"
    lock = load_lock()
    sid = source_id(key, ref)
    if sid in lock["pinned"] and not force:
        return True, f"{sid}  pinned {lock['pinned'][sid]['sha'][:12]} (release to re-sync)"
    d = clone_dir(key, ref)
    try:
        fetch_ref, resolved = resolve_ref(url, ref)
        if not (d / ".git").exists():
            d.parent.mkdir(parents=True, exist_ok=True)
            git_ok(["clone", "--depth", "1", "--branch", fetch_ref, url, str(d)])
        else:
            git_ok(["-C", str(d), "fetch", "--depth", "1", "origin", fetch_ref])
            git_ok(["-C", str(d), "reset", "--hard", "FETCH_HEAD"])
        sha = git_ok(["-C", str(d), "rev-parse", "HEAD"]).stdout.strip()
    except SystemExit:
        # clean partial clone so the next run can retry cleanly
        if d.exists() and not (d / ".git").exists():
            import shutil; shutil.rmtree(d, ignore_errors=True)
        return False, f"{sid}  FAILED (see above)"
    lock["pinned"][sid] = {"sha": sha, "ref": ref, "resolved": resolved, "url": url}
    save_lock(lock)
    return True, f"{sid}  {sha[:12]}  {d.relative_to(BASE)}"

# ---- commands ----
def cmd_sync(args):
    reg = load_registry()
    if not reg["repos"]:
        die(f"no repos in {REPOS_YAML}; run: repo.py add <owner/repo> <url> [ref]")
    if args.force:
        LOCK_YAML.unlink(missing_ok=True)
    keys = args.sources or list(reg["repos"].keys())
    print(f"sync -> {LOCK_YAML.name}")
    failures = []
    for k in keys:
        if k not in reg["repos"]:
            print(f"  {k}  FAILED not in registry"); failures.append(k); continue
        ok, detail = reconcile(k, reg["repos"][k], force=args.force)
        print(f"  {detail}")
        if not ok:
            failures.append(k)
    if failures:
        die(f"{len(failures)} source(s) failed: {', '.join(failures)}", code=1)

def cmd_status(args):
    lock = load_lock()
    if not lock["pinned"]:
        print("no active lock"); return
    print(f"active lock -> {LOCK_YAML}")
    for sid, info in sorted(lock["pinned"].items()):
        print(f"  {sid}  {info['sha'][:12]}  resolved={info.get('resolved', info.get('ref'))}")

def cmd_release(args):
    LOCK_YAML.unlink(missing_ok=True)
    print("lock released (clones kept)")

def cmd_add(args):
    reg = load_registry()
    key = args.key
    if key in reg["repos"]:
        die(f"already in registry: {key}")
    reg["repos"][key] = {
        "url": args.url,
        "ref": args.ref or "main",
        **({"include": args.include} if args.include else {}),
        **({"ignore": args.ignore} if args.ignore else {}),
    }
    save_registry(reg)
    print(f"added {key} -> {args.url} (ref={args.ref or 'main'})")

def cmd_list(args):
    reg = load_registry()
    if not reg["repos"]:
        print("registry empty"); return
    print(f"registry -> {REPOS_YAML}")
    for key, spec in sorted(reg["repos"].items()):
        line = f"  {key}@{spec.get('ref','main')}  {spec.get('url')}"
        if spec.get("include") or spec.get("ignore"):
            line += f"  include={spec.get('include')} ignore={spec.get('ignore')}"
        print(line)

def cmd_remove(args):
    reg = load_registry()
    if args.key not in reg["repos"]:
        die(f"not in registry: {args.key}")
    del reg["repos"][args.key]
    save_registry(reg)
    print(f"removed {args.key} from registry (clone kept)")

def cmd_path(args):
    reg = load_registry()
    if args.key not in reg["repos"]:
        die(f"not in registry: {args.key}")
    print(clone_dir(args.key, reg["repos"][args.key].get("ref", "main")))

def main():
    p = argparse.ArgumentParser(prog="repo.py", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sync", help="clone/fetch latest; pin commits in lock.yaml")
    s.add_argument("sources", nargs="*"); s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_sync)
    sub.add_parser("status", help="show pinned commits").set_defaults(func=cmd_status)
    sub.add_parser("release", help="drop lock.yaml (clones persist)").set_defaults(func=cmd_release)
    a = sub.add_parser("add", help="register a repo")
    a.add_argument("key"); a.add_argument("url"); a.add_argument("ref", nargs="?")
    a.add_argument("--include", nargs="*"); a.add_argument("--ignore", nargs="*")
    a.set_defaults(func=cmd_add)
    sub.add_parser("list", help="list registry").set_defaults(func=cmd_list)
    r = sub.add_parser("remove", help="unregister a repo"); r.add_argument("key")
    r.set_defaults(func=cmd_remove)
    pp = sub.add_parser("path", help="print clone dir for a repo"); pp.add_argument("key")
    pp.set_defaults(func=cmd_path)
    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
