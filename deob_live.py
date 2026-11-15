#!/usr/bin/env python3
# --discord.gg/Nkkq33F8GY--
"""deob_live - recover constants and strings from layered LuaU VM protectors.

The samples this targets are generated as one enormous statement: an alias
header, a base-N constant-pool decoder, a stream-cipher string decryptor, then
the VM itself. All of that plaintext is built at load time, so instead of
guessing the cipher this executes the loader and records what it decrypts.

How it works
------------
1. every `local function NAME(...)` definition in the target gets a thin wrapper
   that records each return value (the decryptors, pool builders and blob
   decoders all return the plaintext they produced);
2. the target is replayed inside `local function __replay()` in a real LuaU
   runtime (luau.exe), so `buffer`, `bit32` and the stream ciphers behave exactly
   as they do in Roblox;
3. the replay stops at the first thing that needs a real Roblox API -- and by
   then the loader has already handed us its constants;
4. everything captured is written out: plaintext strings, decoded blobs, and the
   first bytes of any binary payload (bytecode detection included).

    python deob_live.py target.lua --out out_live
    python deob_live.py target.lua --stubs --timeout 180   # go past game/Enum use
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HOME = Path(__file__).resolve().parent
LUAU = Path(os.environ.get("LUAU") or (HOME / "_tools" / "luau" / "luau.exe"))

OPENERS = {"function", "if", "do", "repeat"}
CLOSERS = {"end", "until"}



def tokens(src: str, start: int = 0):
    i, n = start, len(src)
    while i < n:
        c = src[i]
        if c in "\"'":
            q = c
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == q:
                    break
                j += 1
            yield "string", src[i:j + 1], i, j + 1
            i = j + 1
            continue
        if c == "-" and src.startswith("--", i):
            j = src.find("\n", i)
            j = n if j < 0 else j
            yield "comment", "", i, j
            i = j + 1
            continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1
            yield "word", src[i:j], i, j
            i = j
            continue
        if c.isdigit():
            j = i
            while j < n and (src[j].isalnum() or src[j] in "._"):
                j += 1
            yield "number", src[i:j], i, j
            i = j
            continue
        yield "punct", c, i, i + 1
        i += 1


def block_end(src: str, open_pos: int) -> int:
    """Offset just past the block that starts at open_pos."""
    depth = 0
    for kind, text, _s, e in tokens(src, open_pos):
        if kind != "word":
            continue
        if text in OPENERS:
            depth += 1
        elif text in CLOSERS:
            depth -= 1
            if depth == 0:
                return e
    return -1


def find_local_functions(src: str) -> list[tuple[str, int, int]]:
    """(name, start, end) for every `local function NAME(` definition."""
    out = []
    for m in re.finditer(r"local\s+function\s+(\w+)\s*\(", src):
        end = block_end(src, m.start())
        if end > 0:
            out.append((m.group(1), m.start(), end))
    return out



PRELUDE = r"""
local __realbuf = buffer
local function __hex(s)
  local t = table.create(#s)
  for i = 1, #s do t[i] = string.format("%02x", string.byte(s, i)) end
  return table.concat(t)
end
local __seen = {}
local __CAP = 900000   -- hex chars; enough for the largest payload in these builds
local function __dump(name, v)
  local tv = type(v)
  local key
  if tv == "string" then
    key = name .. ":" .. #v
    if __seen[key] then return end
    __seen[key] = true
    print(string.format("@@V %s string %d %s", name, #v, __hex(string.sub(v, 1, __CAP))))
  elseif tv == "buffer" then
    local n = __realbuf.len(v)
    key = name .. ":" .. n
    if __seen[key] then return end
    __seen[key] = true
    print(string.format("@@V %s buffer %d %s", name, n, __hex(__realbuf.readstring(v, 0, n))))
  elseif tv == "table" then
    local n = 0
    for _ in pairs(v) do n += 1 end
    key = name .. ":" .. n
    if __seen[key] then return end
    __seen[key] = true
    print(string.format("@@V %s table %d", name, n))
  elseif tv == "number" or tv == "boolean" then
    print(string.format("@@V %s value %s", name, tostring(v)))
  end
end
local function __rec(name, ...)
  if select("#", ...) > 0 then __dump(name, ...) end
  return ...
end
"""

STUBS = r"""
local __stubcache = {}
local function __mkstub(name, depth)
  depth = depth or 0
  if depth > 6 then return 0 end
  local cached = __stubcache[name]
  if cached then return cached end
  local t = {}
  local mt = {}
  mt.__index = function(_, k) return __mkstub(name .. "." .. tostring(k), depth + 1) end
  mt.__newindex = function() end
  mt.__call = function() return __mkstub(name .. "()") end
  mt.__tostring = function() return name end
  mt.__len = function() return 0 end
  mt.__add = function() return 0 end
  mt.__sub = function() return 0 end
  mt.__mul = function() return 1 end
  mt.__div = function() return 1 end
  mt.__mod = function() return 0 end
  mt.__pow = function() return 0 end
  mt.__unm = function() return 0 end
  mt.__concat = function(a, b) return tostring(a) .. tostring(b) end
  mt.__eq = function() return false end
  mt.__lt = function() return false end
  mt.__le = function() return false end
  setmetatable(t, mt)
  __stubcache[name] = t
  return t
end
local game = __mkstub("game")
local workspace = __mkstub("workspace")
local script = __mkstub("script")
local Instance = __mkstub("Instance")
local Vector3 = __mkstub("Vector3")
local Vector2 = __mkstub("Vector2")
local Vector3int16 = __mkstub("Vector3int16")
local CFrame = __mkstub("CFrame")
local Color3 = __mkstub("Color3")
local BrickColor = __mkstub("BrickColor")
local UDim = __mkstub("UDim")
local UDim2 = __mkstub("UDim2")
local Ray = __mkstub("Ray")
local Rect = __mkstub("Rect")
local Region3 = __mkstub("Region3")
local NumberRange = __mkstub("NumberRange")
local NumberSequence = __mkstub("NumberSequence")
local NumberSequenceKeypoint = __mkstub("NumberSequenceKeypoint")
local ColorSequence = __mkstub("ColorSequence")
local ColorSequenceKeypoint = __mkstub("ColorSequenceKeypoint")
local TweenInfo = __mkstub("TweenInfo")
local Enum = __mkstub("Enum")
local Axes = __mkstub("Axes")
local Faces = __mkstub("Faces")
local PhysicalProperties = __mkstub("PhysicalProperties")
local Random = __mkstub("Random")
local DateTime = __mkstub("DateTime")
local Font = __mkstub("Font")
local Path2DControlPoint = __mkstub("Path2DControlPoint")
local CatalogSearchParams = __mkstub("CatalogSearchParams")
local task = { spawn = function(f, ...) return f(...) end,
               defer = function(f, ...) return f(...) end,
               delay = function() end, wait = function() end, cancel = function() end }
local wait = function() return 0 end
local spawn = function(f, ...) return f(...) end
local delay = function() end
local tick = function() return 0 end
local time = function() return 0 end
"""


def call_end(src: str, open_paren: int) -> int:
    """Offset just past the ')' that closes the '(' at open_paren."""
    depth = 0
    i = open_paren
    n = len(src)
    while i < n:
        c = src[i]
        if c in "\"'":
            q = c
            i += 1
            while i < n:
                if src[i] == "\\":
                    i += 2
                    continue
                if src[i] == q:
                    break
                i += 1
            i += 1
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


def wrap_decryptor_calls(src: str) -> tuple[str, int]:
    """Turn `dec("<cipher>", seed)` into `__rec("dec", dec("<cipher>", seed))`.

    Only calls whose callee is a locally defined function and whose first
    argument is a string literal long enough to be a ciphertext are touched.
    Outermost calls win, so a decryptor that feeds a decoder is recorded once
    with its final value.
    """
    defined = {m.group(1) for m in re.finditer(r"local\s+function\s+(\w+)\s*\(", src)}
    spans: list[tuple[int, int, str]] = []
    for m in re.finditer(r"\b(\w+)\s*\(", src):
        name = m.group(1)
        if name not in defined:
            continue
        open_paren = m.end() - 1
        j = open_paren + 1
        while j < len(src) and src[j] in " \t\n":
            j += 1
        if j >= len(src) or src[j] not in "\"'":
            continue
        q = src[j]
        k = j + 1
        while k < len(src):
            if src[k] == "\\":
                k += 2
                continue
            if src[k] == q:
                break
            k += 1
        literal_len = k - j - 1
        if literal_len < 8:
            continue
        end = call_end(src, open_paren)
        if end < 0:
            continue
        spans.append((m.start(), end, name))

    spans.sort()
    outer: list[tuple[int, int, str]] = []
    for start, end, name in spans:
        if outer and start < outer[-1][1]:
            continue
        outer.append((start, end, name))

    out = []
    cursor = 0
    for start, end, name in outer:
        out.append(src[cursor:start])
        out.append(f'__rec({name!r}, ' + src[start:end] + ")")
        cursor = end
    out.append(src[cursor:])
    return "".join(out), len(outer)


def build_harness(src: str, stubs: bool) -> tuple[str, int]:
    wrapped, count = wrap_decryptor_calls(src)
    parts = [PRELUDE]
    if stubs:
        parts.append(STUBS)
    parts.append(wrapped)
    return "\n".join(parts), count


def run_luau(code: str, path: Path, timeout: float) -> tuple[int, str, str]:
    path.write_text(code, encoding="utf-8", newline="\n")
    try:
        proc = subprocess.run([str(LUAU), str(path)], capture_output=True, text=True,
                              errors="replace", timeout=timeout)
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout if isinstance(exc.stdout, str) else ""
        err = exc.stderr if isinstance(exc.stderr, str) else ""
        return -9, out or "", (err or "") + f"\n[timeout after {timeout}s]"



PRINTABLE = set(range(32, 127)) | {9, 10, 13}


def printable_ratio(data: bytes) -> float:
    return sum(1 for b in data if b in PRINTABLE) / len(data) if data else 0.0


def looks_bytecode(data: bytes) -> bool:
    return data[:4] in (b"\x1bLua", b"\x1bLuaT") or data[:4] == b"LUAU" or \
        re.match(rb"^[\x00-\x08\x0b\x0c\x0e-\x1f]{2}", data[:2]) is not None and printable_ratio(data) < 0.2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="deob_live", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--out", default=str(HOME / "out_live"))
    ap.add_argument("--stubs", action="store_true",
                    help="keep the replay alive past Roblox API calls")
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--no-blobs", action="store_true", help="skip binary payload dumps")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    if not LUAU.is_file():
        print(f"luau runtime not found at {LUAU}\n"
              f"run `python deob.py setup` once, or point the LUAU env var at luau.exe",
              file=sys.stderr)
        return 3

    src_path = Path(args.file)
    src = src_path.read_text(encoding="utf-8", errors="replace")
    outdir = Path(args.out) / src_path.stem
    outdir.mkdir(parents=True, exist_ok=True)

    funcs = find_local_functions(src)
    if not funcs:
        print("no local function definitions found - not this protector's shape", file=sys.stderr)
        return 2

    code, wrapped = build_harness(src, args.stubs)
    work = HOME / "work"
    work.mkdir(exist_ok=True)
    harness = work / f"_live_{src_path.stem}.luau"
    rc, stdout, stderr = run_luau(code, harness, args.timeout)

    values: list[tuple[str, str, bytes]] = []
    error = ""
    for line in stdout.splitlines():
        if line.startswith("@@V "):
            parts = line.split(" ", 3)
            if len(parts) < 4:
                continue
            name, kind, payload = parts[1], parts[2], parts[3]
            if kind == "string":
                _size, _, hexs = payload.partition(" ")
                try:
                    values.append((name, "string", bytes.fromhex(hexs)))
                except ValueError:
                    pass
            elif kind == "buffer":
                _size, _, hexs = payload.partition(" ")
                try:
                    values.append((name, "buffer", bytes.fromhex(hexs)))
                except ValueError:
                    pass
            elif kind == "table":
                values.append((name, "table", payload.encode()))
            elif kind == "value":
                values.append((name, "value", payload.encode("utf-8", "replace")))
        elif line.startswith("@@ERR "):
            error = line[6:]
    if not error:
        error = "\n".join(stderr.strip().splitlines()[:4])

    strings = [(n, d) for n, k, d in values if k == "string" and len(d) >= 2]
    blobs = [(n, d) for n, d in strings if len(d) >= 48 and printable_ratio(d) < 0.8]
    plain = [(n, d) for n, d in strings if (n, d) not in blobs]

    (outdir / "blobs").mkdir(exist_ok=True)
    manifest = []
    if not args.no_blobs:
        for i, (name, data) in enumerate(blobs):
            safe = re.sub(r"\W+", "_", name) or "blob"
            path = outdir / "blobs" / f"{i:03d}_{safe}.bin"
            path.write_bytes(data)
            manifest.append({"name": name, "file": path.name, "size": len(data),
                             "printable": round(printable_ratio(data), 3),
                             "bytecode": looks_bytecode(data), "head": data[:48].hex(" ")})

    seen: set[bytes] = set()
    lines: list[str] = []
    for name, data in plain:
        if data in seen:
            continue
        seen.add(data)
        lines.append(f"{name}\t{data.decode('latin-1')}")

    (outdir / "strings.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    quoted = []
    for i, line in enumerate(lines, 1):
        text = line.split("\t", 1)[1] if "\t" in line else line
        safe = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
        quoted.append(f'  [{i}] = "{safe}",')
    (outdir / "recovered_strings.lua").write_text(
        f"-- deob_live: plaintext recovered from {src_path.name}\n"
        "-- every entry is a string the loader decrypted at load time\n"
        "return {\n" + "\n".join(quoted) + "\n}\n",
        encoding="utf-8")
    (outdir / "values.txt").write_text(
        "\n".join(f"{n}\t{k}\t{len(d)}\t{d.decode('latin-1')[:120]!r}" for n, k, d in values) + "\n",
        encoding="utf-8")
    (outdir / "blobs.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    report = {
        "input": str(src_path),
        "bytes": len(src),
        "hooks": len(funcs),
        "recorded_calls": wrapped,
        "values": len(values),
        "strings": len(lines),
        "blobs": len(manifest),
        "stubs": args.stubs,
        "exit": rc,
        "error": error,
    }
    (outdir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    if not args.quiet:
        print(f"file      : {src_path}")
        print(f"functions : {len(funcs)} defined, {wrapped} calls recorded")
        print(f"values    : {len(values)}")
        print(f"strings   : {len(lines)} unique plaintext")
        print(f"blobs     : {len(manifest)} binary payloads")
        if error:
            print(f"stopped   : {error.splitlines()[0][:140]}")
        print(f"output    : {outdir}")
        print()
        print("plaintext recovered:")
        for line in lines[:40]:
            print("   ", line[:120])
        if manifest:
            print()
            print("binary payloads:")
            for m in manifest[:10]:
                flag = "bytecode" if m["bytecode"] else "binary  "
                print(f"    {m['file']:<34} {m['size']:>8}B {flag} {m['head'][:40]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
