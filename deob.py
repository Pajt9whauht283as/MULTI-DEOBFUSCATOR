#!/usr/bin/env python3
"""deob - one front-end over every bundled Lua deobfuscator.

    python deob.py list                      what is installed, what is ready
    python deob.py detect <file.lua>         fingerprint the obfuscator
    python deob.py run <file.lua>            auto-detect, run the matching engine
    python deob.py run <file.lua> --all      run every engine, keep every dump
    python deob.py run <file.lua> -e hercules -o clean.lua
    python deob.py build                     build the .NET engines
    python deob.py selftest                  each engine against its own samples
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

HOME = Path(__file__).resolve().parent
VENDOR = HOME / "_engines"
OUTDIR = HOME / "out"
BUILD = HOME / "_build"

TEXT_EXT = {".lua", ".luau", ".luac", ".txt"}
PY = sys.executable or "python"


# --------------------------------------------------------------------------- #
# engine registry
# --------------------------------------------------------------------------- #

@dataclass
class Engine:
    key: str
    name: str
    target: str
    kind: str                       # py | node | dotnet
    root: str                       # relative to _engines
    entry: str                      # relative to root
    args: list[str]                 # {in} {out} {outdir} placeholders
    ext: str = ".lua"
    markers: list[tuple[str, str]] = field(default_factory=list)
    requires: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    fallback_args: list[str] | None = None
    notes: str = ""


ENGINES: dict[str, Engine] = {}


def _add(e: Engine) -> None:
    ENGINES[e.key] = e


_add(Engine(
    key="prometheus",
    name="Prometheus Deobfuscator",
    target="Prometheus",
    kind="node",
    root="Prometheus-Deobfuscator-main/Prometheus-Deobfuscator-main",
    entry="bin/pdeobf.js",
    args=["{in}", "-o", "{out}"],
    markers=[
        (r"prometheus", "prometheus name"),
        (r"--\s*Obfuscated (?:by|with) Prometheus", "prometheus banner"),
        (r"\bgoto\b|::\w+::", "lua goto flattening (prometheus trait)"),
    ],
))

_add(Engine(
    key="hercules",
    name="Hercules Deobfuscator",
    target="Hercules 1.6.x - 2.0.1",
    kind="py",
    root="hercules-deobfuscator-main/hercules-deobfuscator-main/hercules/deobfhercules_fixed",
    entry="deobfhercules.py",
    args=["{in}", "{out}"],
    markers=[
        (r"hercules", "hercules name"),
        (r"Hercules\s+Obfuscator", "hercules banner"),
    ],
))

_add(Engine(
    key="ironveil",
    name="Ironveil V1 Deobfuscator",
    target="Ironveil v1",
    kind="node",
    root="Ironveil-Deobfuscator-V1-main/Ironveil-Deobfuscator-V1-main/deobfuscator",
    entry="index.js",
    args=["{in}", "{out}"],
    markers=[
        (r"ironveil", "ironveil name"),
    ],
))

_add(Engine(
    key="luaobfuscator",
    name="LuaObfuscator Deobfuscator",
    target="LuaObfuscator Chaotic Good / Chaotic Evil",
    kind="node",
    root="LuaObfuscator-Deobfuscator-main/LuaObfuscator-Deobfuscator-main",
    entry="index.js",
    args=["{in}", "--out", "{out}"],
    markers=[
        (r"chaotic\s*good|chaotic\s*evil", "luaobfuscator tier marker"),
        (r"luaobfuscator", "luaobfuscator name"),
    ],
))

_add(Engine(
    key="luraph15",
    name="Luraph v15 Deobfuscator (Node + Python devirt)",
    target="Luraph v15.x",
    kind="node",
    root="LuraphV15_1_Deobfuscator_Newest-main/LuraphV15_1_Deobfuscator_Newest-main",
    entry="deob.js",
    args=["{in}", "-o", "{out}", "--strings"],
    markers=[
        (r"This file was protected using Luraph Obfuscator v15", "luraph v15 banner"),
        (r"Luraph Obfuscator v15", "luraph v15 banner"),
    ],
    notes="needs python on PATH for the symbolic devirt bridge",
))

_add(Engine(
    key="luraph14",
    name="Luraph v14.7 Deobfuscator (Node + Python devirt)",
    target="Luraph v14.7",
    kind="node",
    root="Luraph_Deobfuscator_Sources/Luraph_Deobfuscator_Sources/v14.7_experimental_source",
    entry="deob.js",
    args=["{in}", "-o", "{out}", "--strings"],
    markers=[
        (r"This file was protected using Luraph Obfuscator v14\.7", "luraph v14.7 banner"),
    ],
    notes="needs python on PATH for the symbolic devirt bridge",
))

_add(Engine(
    key="luraph_py",
    name="Luraph 14.7/14.8/14.9 Framework",
    target="Luraph v14.7 / v14.8 / v14.9 (+ IronBrew1 module)",
    kind="py",
    root="luraph-v15-v14.x-deobfuscator-main/luraph-v15-v14.x-deobfuscator-main/Deobfuscator/deobf",
    entry="cli.py",
    args=["{in}", "-o", "{out}", "--strings"],
    markers=[
        (r"This file was protected using Luraph Obfuscator v14\.[789]", "luraph v14 banner"),
        (r"^\s*local init = \(function\(\.\.\.", "luraph v14.8 init shape"),
    ],
    fallback_args=["{in}", "-o", "{out}", "--strings", "--trace-fallback"],
    notes="falls back to a behaviour trace when full devirt bails",
))

_add(Engine(
    key="ferib",
    name="Ferib / LuaObfuscator.com VM Deobfuscator",
    target="LuaObfuscator.com (Ferib) VM-protected scripts",
    kind="py",
    root="luraph-v15-v14.x-deobfuscator-main/luraph-v15-v14.x-deobfuscator-main",
    entry="deobfuscate.py",
    args=["{in}", "-o", "{out}"],
    markers=[
        (r"luaobfuscator\.com|ferib", "ferib signature"),
    ],
    notes="generic symbolic lifter, no banner required",
))

_add(Engine(
    key="fuscator77",
    name="77fuscator Deobfuscator",
    target="77fuscator 0.6.x",
    kind="dotnet",
    root="77fuscatorDeobfuscator-main/77fuscatorDeobfuscator-main",
    entry="deobfuscator.csproj",
    args=["{in}", "-o", "{out}", "--strings"],
    ext=".luac",
    markers=[
        (r"77FUS\|", "77fuscator blob header"),
        (r"77fuscator", "77fuscator name"),
    ],
    requires=("dotnet",),
))

_add(Engine(
    key="moonsec",
    name="Moonsec Deobfuscator",
    target="Moonsec v3",
    kind="dotnet",
    root="MoonsecDeobfuscator-master/MoonsecDeobfuscator-master",
    entry="MoonsecDeobfuscator.csproj",
    args=["-dev", "-i", "{in}", "-o", "{out}"],
    markers=[
        (r"moonsec", "moonsec name"),
        (r"MoonSec\s*V\d", "moonsec banner"),
    ],
    requires=("dotnet",),
))

_add(Engine(
    key="centurion",
    name="Centurion Polymorphic Deobfuscator",
    target="Centurion / Luraph v6.x packs",
    kind="py",
    root="centurion-deobfuscator/centurion-deobfuscator",
    entry="centurion.py",
    args=["deobfuscate", "{in}", "--out-dir", "{outdir}"],
    markers=[
        (r"centurion", "centurion name"),
    ],
    env={
        "CENT_LUAU_LUAU": "{tools}/luau.exe",
        "CENT_LUAU_LUAU_COMPILE": "{tools}/luau-compile.exe",
        "CENT_LUAU_LUAU_AST": "{tools}/luau-ast.exe",
        "CENT_SANDBOX": "{vendor}/luraph-v15-v14.x-deobfuscator-main/luraph-v15-v14.x-deobfuscator-main/Deobfuscator/deobf",
        "CENT_SAMPLES": "{vendor}/centurion-deobfuscator/centurion-deobfuscator/samples",
    },
    notes="wants luau binaries (auto-provisioned into _tools/luau)",
))

_add(Engine(
    key="layered",
    name="Layered LuaU VM (live constant recovery)",
    target="multi-layer LuaU VM protectors (alias header + base-N pools)",
    kind="py",
    root="",
    entry="deob_live.py",
    args=["{in}", "--out", "{outdir}", "--stubs"],
    markers=[
        (r"local \w+=rawset local \w+=game", "multi-layer alias header"),
        (r"\[\d{6,8}\]\[\d{6,8}\]", "two-level constant pool"),
    ],
    notes="runs the loader in luau and records every decrypted constant",
))

AUTO_ORDER = [
    "luraph15", "luraph14", "luraph_py", "ferib",
    "prometheus", "hercules", "ironveil", "luaobfuscator",
    "fuscator77", "moonsec", "centurion", "layered",
]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def engine_root(e: Engine) -> Path:
    return HOME if not e.root else VENDOR / e.root


def tool_version(cmd: str) -> str | None:
    try:
        r = subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=20)
        line = (r.stdout or r.stderr).strip().splitlines()
        return line[0].strip() if line else "present"
    except Exception:
        try:
            r = subprocess.run([cmd, "-v"], capture_output=True, text=True, timeout=20)
            line = (r.stdout or r.stderr).strip().splitlines()
            return line[0].strip() if line else "present"
        except Exception:
            return None


def dotnet_exe(e: Engine) -> Path | None:
    target = BUILD / e.key
    if not target.is_dir():
        return None
    for pat in ("*.exe", "*.dll"):
        hits = sorted(target.glob(pat))
        if hits:
            return hits[0]
    return None


LUAU_DIR = HOME / "_tools" / "luau"
LUAU_TAG = "0.747"


def ensure_luau() -> tuple[bool, str]:
    exe = LUAU_DIR / "luau.exe"
    if exe.is_file():
        return True, str(exe)
    import io
    import urllib.request
    import zipfile

    LUAU_DIR.mkdir(parents=True, exist_ok=True)
    url = f"https://github.com/luau-lang/luau/releases/download/{LUAU_TAG}/luau-windows.zip"
    try:
        with urllib.request.urlopen(url, timeout=120) as resp:
            blob = resp.read()
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            zf.extractall(LUAU_DIR)
    except Exception as exc:                            # noqa: BLE001
        return False, f"download failed: {exc}"
    return exe.is_file(), str(exe)


def engine_ready(e: Engine) -> tuple[bool, str]:
    root = engine_root(e)
    if not root.is_dir():
        return False, "source missing"
    if e.env and not (LUAU_DIR / "luau.exe").is_file():
        return False, "luau binaries missing (run: python deob.py setup)"
    if e.kind == "dotnet":
        exe = dotnet_exe(e)
        if exe is None:
            return False, "not built (run: python deob.py build)"
        if shutil.which("dotnet") is None:
            return False, "dotnet not on PATH"
        return True, "built"
    if not (root / e.entry).is_file():
        return False, f"entry missing: {e.entry}"
    if e.kind == "node" and shutil.which("node") is None:
        return False, "node not on PATH"
    if e.kind == "py" and not Path(PY).exists():
        return False, "python not found"
    return True, "ready"


def build_engine(e: Engine, verbose: bool = False) -> tuple[bool, str]:
    if e.kind != "dotnet":
        return True, "nothing to build"
    root = engine_root(e)
    proj = root / e.entry
    if not proj.is_file():
        return False, f"project missing: {proj}"
    if shutil.which("dotnet") is None:
        return False, "dotnet not on PATH"

    outdir = BUILD / e.key
    cmd = ["dotnet", "build", str(proj), "-c", "Release", "-o", str(outdir), "-nologo", "-v", "q"]
    r = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True)
    if r.returncode != 0 and "NETSDK1045" in (r.stdout + r.stderr):
        # newer target framework than the installed SDK: retarget a private copy
        work = BUILD / f"{e.key}_src"
        if work.exists():
            shutil.rmtree(work)
        shutil.copytree(root, work, ignore=shutil.ignore_patterns("bin", "obj"))
        proj2 = work / e.entry
        text = proj2.read_text(encoding="utf-8")
        text = re.sub(r"<TargetFramework>net\d+\.\d+</TargetFramework>",
                      "<TargetFramework>net8.0</TargetFramework>", text)
        proj2.write_text(text, encoding="utf-8")
        cmd = ["dotnet", "build", str(proj2), "-c", "Release", "-o", str(outdir), "-nologo", "-v", "q"]
        r = subprocess.run(cmd, cwd=str(work), capture_output=True, text=True)
    if r.returncode != 0 or dotnet_exe(e) is None:
        tail = "\n".join((r.stdout + r.stderr).strip().splitlines()[-12:])
        return False, tail or "build failed"
    return True, str(dotnet_exe(e))


def build_command(e: Engine, src: Path, out: Path, outdir: Path) -> list[str]:
    if e.kind == "dotnet":
        exe = dotnet_exe(e)
        if exe is None:
            raise RuntimeError(f"{e.key}: not built")
        base = [str(exe)] if exe.suffix.lower() == ".exe" else ["dotnet", str(exe)]
    elif e.kind == "node":
        base = ["node", str(engine_root(e) / e.entry)]
    else:
        base = [PY, str(engine_root(e) / e.entry)]

    subs = {"{in}": str(src), "{out}": str(out), "{outdir}": str(outdir)}
    for a in e.args:
        base.append(subs.get(a, a))
    return base


def engine_env(e: Engine) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    subs = {
        "{tools}": str(HOME / "_tools" / "luau"),
        "{vendor}": str(VENDOR),
        "{home}": str(HOME),
    }
    for k, v in e.env.items():
        for pat, rep in subs.items():
            v = v.replace(pat, rep)
        env[k] = v
    return env


def render_args(e: Engine, args: list[str], src: Path, out: Path, outdir: Path) -> list[str]:
    full = build_command(e, src, out, outdir)
    head = len(full) - len(e.args)
    subs = {"{in}": str(src), "{out}": str(out), "{outdir}": str(outdir)}
    return full[:head] + [subs.get(a, a) for a in args]


def snapshot(d: Path) -> dict[Path, float]:
    if not d.is_dir():
        return {}
    return {p: p.stat().st_mtime for p in d.rglob("*") if p.is_file()}


JUNK_TOKENS = ("harness", ".trace.", ".raw.", "_index", "probe", "_log")
GOOD_TOKENS = ("reconstructed", "clean", "beautified", "maximal", "deobf", "output", "final")


def rank_output(path: Path) -> tuple[int, int]:
    name = path.name.lower()
    score = 0
    if path.suffix.lower() in (".lua", ".luac", ".luau"):
        score += 10
    elif path.suffix.lower() in TEXT_EXT:
        score += 2
    if path.suffix.lower() == ".luac":
        score += 4
    if any(t in name for t in JUNK_TOKENS):
        score -= 60
    if any(t in name for t in GOOD_TOKENS):
        score += 20
    return score, path.stat().st_size


def pick_primary(before: dict[Path, float], outdir: Path, wanted: Path) -> Path | None:
    after = snapshot(outdir)
    new = [p for p in after if p not in before or after[p] > before.get(p, 0)]
    if not new:
        new = list(after)
    new = [p for p in new if p.name != "_log.txt" and p.stat().st_size > 0]
    if not new:
        return None
    if wanted.is_file() and wanted.stat().st_size > 0 and wanted in new:
        return wanted
    return max(new, key=rank_output)


# --------------------------------------------------------------------------- #
# detection
# --------------------------------------------------------------------------- #

def fingerprint(text: str) -> list[tuple[str, int, str]]:
    head = text[:200_000]
    scored: dict[str, tuple[int, list[str]]] = {}
    low = head.lower()

    for e in ENGINES.values():
        score, why = 0, []
        for pattern, label in e.markers:
            flags = re.MULTILINE | re.IGNORECASE
            n = len(re.findall(pattern, head, flags))
            if n:
                score += 3 if label.startswith(("luraph", "77fuscator", "moonsec", "hercules", "ironveil", "prometheus")) else 1
                score += min(n - 1, 4)
                why.append(f"{label} x{n}" if n > 1 else label)
        if score:
            scored[e.key] = (score, why)

    # shape-only fallbacks, no banner present
    if "luraph" not in scored and re.search(r"\[\d+\]\s*=\s*(?:bit32|buffer)\.\w+", head):
        scored.setdefault("ferib", (1, ["VM shape: opcode table over bit32/buffer"]))
    if "return setmetatable({" in low and "lph" in low:
        s = scored.get("luraph15", (0, []))
        scored["luraph15"] = (max(s[0], 2), s[1] + ["LPH marker"])
    if re.search(r"\[\d{2,3}\]\s*=\s*function\s*\(\s*\w+\s*,\s*\w+\s*\)", head) and len(head) > 20000:
        for k in ("prometheus", "hercules", "ironveil"):
            if k not in scored:
                scored[k] = (1, ["generic VM: opcode dispatch table"])

    out = [(k, v[0], ", ".join(dict.fromkeys(v[1]))) for k, v in scored.items()]
    out.sort(key=lambda t: (-t[1], AUTO_ORDER.index(t[0]) if t[0] in AUTO_ORDER else 99))
    return out


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #

def cmd_list(args) -> int:
    print(f"vendor: {VENDOR}")
    print(f"output: {OUTDIR}")
    print()
    head = f"{'key':<14} {'target':<44} {'lang':<8} {'status':<8} notes"
    print(head)
    print("-" * len(head))
    ready = 0
    for key in sorted(ENGINES, key=lambda k: AUTO_ORDER.index(k) if k in AUTO_ORDER else 99):
        e = ENGINES[key]
        ok, status = engine_ready(e)
        ready += ok
        print(f"{e.key:<14} {e.target:<44} {e.kind:<8} {(status if ok else 'missing'):<8} {e.notes}")
        if not ok:
            print(f"{'':<14} -> {status}")
    print()
    print(f"{ready}/{len(ENGINES)} engines ready")
    if ready == 0:
        print()
        print("no engine sources yet - put each engine under _engines/<key>/ "
              "(see docs/ENGINES.md)")
    return 0


def cmd_detect(args) -> int:
    src = Path(args.file)
    if not src.is_file():
        print(f"no such file: {src}", file=sys.stderr)
        return 2
    text = src.read_text(encoding="utf-8", errors="replace")
    hits = fingerprint(text)
    print(f"{src.name}  ({len(text)} bytes, {text.count(chr(10)) + 1} lines)")
    if not hits:
        print("no signature matched - run with --all to brute force")
        return 1
    for key, score, why in hits:
        e = ENGINES[key]
        ok, _ = engine_ready(e)
        print(f"  {score:>3}  {key:<14} {e.target:<40} {'ready' if ok else 'not ready'}  [{why}]")
    return 0


def run_engine(e: Engine, src: Path, workdir: Path, timeout: float, verbose: bool) -> dict:
    outdir = workdir / e.key
    if outdir.exists():
        shutil.rmtree(outdir)
    outdir.mkdir(parents=True)
    wanted = outdir / (src.stem + "_deobf" + e.ext)
    before = snapshot(outdir)
    env = engine_env(e)

    attempts = [("primary", e.args)]
    if e.fallback_args:
        attempts.append(("fallback", e.fallback_args))

    log_parts: list[str] = []
    t0 = time.time()
    code, out, err = 0, "", ""
    mode_used = "primary"

    for mode, argset in attempts:
        cmd = render_args(e, argset, src.resolve(), wanted, outdir)
        log_parts.append(f"$ {' '.join(cmd)}")
        try:
            proc = subprocess.run(cmd, cwd=str(engine_root(e)), capture_output=True,
                                  timeout=timeout, text=True, errors="replace", env=env)
            code, out, err = proc.returncode, proc.stdout or "", proc.stderr or ""
        except subprocess.TimeoutExpired as exc:
            code = -9
            out = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
            err = f"timeout after {timeout}s"
        except Exception as exc:                       # noqa: BLE001 - report, don't die
            code, out, err = -1, "", f"{type(exc).__name__}: {exc}"
        log_parts.append(f"--- {mode} stdout ---\n{out}\n--- {mode} stderr ---\n{err}")
        mode_used = mode
        if code == 0 and pick_primary(before, outdir, wanted) is not None:
            break
    dt = time.time() - t0

    (outdir / "_log.txt").write_text(
        f"engine: {e.key}\nexit  : {code}\nmode  : {mode_used}\n\n" + "\n\n".join(log_parts),
        encoding="utf-8")

    primary = pick_primary(before, outdir, wanted)
    files = sorted(p for p in outdir.rglob("*") if p.is_file() and p.name != "_log.txt")
    produced = primary is not None and primary.stat().st_size > 0
    # an engine that "succeeds" with a 15-byte stub on a 200 KB input has not succeeded
    tiny = produced and primary.stat().st_size < 64 and src.stat().st_size > 2048
    ok = produced and code == 0 and mode_used == "primary" and not tiny
    status = "ok" if ok else ("partial" if produced else "fail")
    if verbose:
        tail = (out + err).strip().splitlines()[-6:]
        for line in tail:
            print(f"    | {line}")
    return {
        "engine": e.key,
        "ok": ok,
        "status": status,
        "exit": code,
        "mode": mode_used,
        "seconds": round(dt, 2),
        "primary": str(primary) if primary else None,
        "size": primary.stat().st_size if primary else 0,
        "files": [str(p) for p in files],
        "stderr_tail": "\n".join(err.strip().splitlines()[-4:]),
    }


def cmd_run(args) -> int:
    src = Path(args.file)
    if not src.is_file():
        print(f"no such file: {src}", file=sys.stderr)
        return 2
    text = src.read_text(encoding="utf-8", errors="replace")

    if args.engine:
        keys = []
        for k in args.engine:
            if k not in ENGINES:
                print(f"unknown engine: {k} (see: python deob.py list)", file=sys.stderr)
                return 2
            keys.append(k)
    elif args.all:
        keys = list(AUTO_ORDER)
    else:
        hits = fingerprint(text)
        keys = [k for k, s, _ in hits if s > 0] or list(AUTO_ORDER)
        print(f"detected: {', '.join(hits and [f'{k}({s})' for k, s, _ in hits] or ['nothing - brute forcing'])}")

    tag = hashlib.sha1(str(src.resolve()).encode("utf-8")).hexdigest()[:8]
    workdir = OUTDIR / f"{src.stem}-{tag}"
    workdir.mkdir(parents=True, exist_ok=True)

    results = []
    for key in keys:
        e = ENGINES[key]
        ok, status = engine_ready(e)
        if not ok:
            print(f"[skip] {key}: {status}")
            continue
        print(f"[run ] {key} -> {e.target}")
        res = run_engine(e, src, workdir, args.timeout, args.verbose)
        results.append(res)
        tag = {"ok": " ok ", "partial": "part", "fail": "fail"}[res["status"]]
        if res["ok"]:
            print(f"[{tag}] {key}: {res['size']} bytes in {res['seconds']}s -> {res['primary']}")
            if not args.all:
                break
        elif res["status"] == "partial":
            print(f"[{tag}] {key}: {res['size']} bytes (exit {res['exit']}, incomplete) "
                  f"-> {res['primary']}")
        else:
            print(f"[{tag}] {key}: exit {res['exit']} in {res['seconds']}s"
                  + (f" | {res['stderr_tail'].splitlines()[-1]}" if res["stderr_tail"] else ""))

    (workdir / "report.json").write_text(
        json.dumps({"input": str(src), "results": results}, indent=2), encoding="utf-8")

    wins = [r for r in results if r["ok"]]
    usable = wins or [r for r in results if r["status"] == "partial"]
    if args.out and usable:
        best = max(usable, key=lambda r: (r["ok"], r["size"]))
        shutil.copyfile(best["primary"], args.out)
        print(f"wrote {args.out}  (from {best['engine']}, {best['size']} bytes)")
    elif wins and not args.all:
        print(f"result kept at {wins[0]['primary']}")
    elif args.all:
        print()
        for r in sorted(results, key=lambda r: (-r["size"], r["engine"])):
            mark = {"ok": "ok", "partial": "part", "fail": "fail"}[r["status"]]
            print(f"  {mark:<5} {r['engine']:<14} {r['size']:>9} bytes  {r['seconds']:>6}s")
    return 0 if usable else 1


def cmd_build(args) -> int:
    keys = args.engine or [k for k, e in ENGINES.items() if e.kind == "dotnet"]
    rc = 0
    for key in keys:
        e = ENGINES.get(key)
        if e is None:
            print(f"unknown engine: {key}", file=sys.stderr)
            rc = 2
            continue
        print(f"[build] {key} ...")
        ok, msg = build_engine(e, args.verbose)
        print(f"[{' ok ' if ok else 'fail'}] {key}: {msg.splitlines()[-1] if msg else ''}")
        if not ok:
            rc = 1
            if args.verbose:
                print(msg)
    return rc


def cmd_setup(args) -> int:
    print("[setup] luau binaries ...")
    ok, msg = ensure_luau()
    print(f"[{' ok ' if ok else 'fail'}] luau: {msg}")
    print("[setup] .NET engines ...")
    rc = 0
    for key, e in ENGINES.items():
        if e.kind != "dotnet":
            continue
        if not (engine_root(e) / e.entry).is_file():
            print(f"[skip] {key}: engine sources not present")
            continue
        built, msg = build_engine(e)
        print(f"[{' ok ' if built else 'fail'}] {key}: {msg.splitlines()[-1] if msg else ''}")
        rc |= 0 if built else 1
    return 0 if ok and rc == 0 else 1


def cmd_selftest(args) -> int:
    cases = [
        ("hercules", "hercules-deobfuscator-main/hercules-deobfuscator-main/hercules/deobfhercules_fixed/test_samples/sample_VM.lua"),
        ("ironveil", "Ironveil-Deobfuscator-V1-main/Ironveil-Deobfuscator-V1-main/Samples/obf.lua"),
        ("fuscator77", "77fuscatorDeobfuscator-main/77fuscatorDeobfuscator-main/tests/hello-obfuscated.lua"),
        ("luraph15", "luraph-v15-v14.x-deobfuscator-main/luraph-v15-v14.x-deobfuscator-main/SON.LUA"),
        ("luraph_py", "luraph-v15-v14.x-deobfuscator-main/luraph-v15-v14.x-deobfuscator-main/Deobfuscator/deobf/.SON.luraph_v14_7_work/SON.src.lua"),
        ("luraph14", "luraph-v15-v14.x-deobfuscator-main/luraph-v15-v14.x-deobfuscator-main/Deobfuscator/deobf/.SON.luraph_v14_7_work/SON.src.lua"),
        ("centurion", "centurion-deobfuscator/centurion-deobfuscator/samples/centuration7th.lua"),
    ]
    workdir = OUTDIR / "_selftest"
    workdir.mkdir(parents=True, exist_ok=True)
    fails = 0
    for key, rel in cases:
        e = ENGINES[key]
        ok, status = engine_ready(e)
        sample = VENDOR / rel
        if not sample.is_file():
            print(f"[skip] {key}: sample not bundled ({rel})")
            continue
        if not ok:
            print(f"[skip] {key}: {status}")
            continue
        res = run_engine(e, sample, workdir, args.timeout, args.verbose)
        tag = {"ok": " ok ", "partial": "part", "fail": "fail"}[res["status"]]
        print(f"[{tag}] {key} on {sample.name}: {res['size']} bytes, {res['seconds']}s"
              + (f" ({res['mode']})" if res["mode"] != "primary" else ""))
        fails += 1 if res["status"] == "fail" else 0
    return 0 if fails == 0 else 1


# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="deob", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="show every engine and whether it is ready")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("detect", help="fingerprint an obfuscated file")
    p.add_argument("file")
    p.set_defaults(func=cmd_detect)

    p = sub.add_parser("run", help="deobfuscate")
    p.add_argument("file")
    p.add_argument("-e", "--engine", action="append", help="engine key(s), repeatable")
    p.add_argument("--all", action="store_true", help="run every engine, keep every dump")
    p.add_argument("-o", "--out", help="copy the best result here")
    p.add_argument("--timeout", type=float, default=300.0)
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("setup", help="fetch luau binaries and build the .NET engines")
    p.set_defaults(func=cmd_setup)

    p = sub.add_parser("build", help="build the .NET engines")
    p.add_argument("-e", "--engine", action="append")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("selftest", help="smoke test engines on their bundled samples")
    p.add_argument("--timeout", type=float, default=300.0)
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_selftest)

    args = ap.parse_args(argv)
    OUTDIR.mkdir(parents=True, exist_ok=True)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
