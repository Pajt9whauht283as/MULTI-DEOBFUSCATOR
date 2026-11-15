<div align="center">

# MULTI-DEOBFUSCATOR

**One CLI. Thirteen Lua / Luau deobfuscation engines. Drop a script, get the truth back.**

Detect → dispatch → deobfuscate → dump everything.

![platform](https://img.shields.io/badge/platform-windows%20%7C%20linux%20%7C%20macos-2f81f7?style=flat-square)
![python](https://img.shields.io/badge/python-3.10%2B-3572A5?style=flat-square)
![engines](https://img.shields.io/badge/engines-13-8957e5?style=flat-square)
![status](https://img.shields.io/badge/status-active-2ea043?style=flat-square)
![license](https://img.shields.io/badge/license-MIT-f0b400?style=flat-square)

</div>

---

## Why this exists

Lua obfuscators multiply faster than anyone can keep a toolchain for. Every new
protection drops with its own deobfuscator, its own invocation, its own output
folder, its own failure mode. You end up with thirteen half-remembered commands and
a folder of scripts you cannot tell apart.

MULTI-DEOBFUSCATOR collapses that into one command. It fingerprints the input
against every engine, runs the one that should win, falls through to the next if
it does not, and keeps every artifact with its logs. Nothing is hidden, nothing
is faked: each run ends `ok`, `partial` or `fail`, and you can see exactly why.

```console
$ deob run suspicious.lua
detected: luraph15(6), ferib(1)
[run ] luraph15 -> Luraph v15.x
[ ok ] luraph15: 38344 bytes in 24.9s -> out/suspicious/luraph15/suspicious_deobf.lua
```

```console
$ deob run suspicious.lua --all

  ok    luraph15            38344 bytes   24.9s
  part  luraph14              812 bytes    2.7s
  fail  hercules                0 bytes    0.1s
  fail  prometheus              0 bytes    0.1s
  ...
```

---

## Install

```bash
git clone https://github.com/Pajt9whauht283as/MULTI-DEOBFUSCATOR
cd MULTI-DEOBFUSCATOR

python deob.py setup     # fetches the Luau toolchain, builds the .NET engines
python deob.py list      # shows every engine and its state
```

Engine sources live in `_engines/<key>/` and are not bundled: the runner reports
anything missing instead of pretending it is there, so the suite degrades to the
engines you actually have. `layered` is built in and works out of the box. The
expected layout per engine is in [docs/ENGINES.md](docs/ENGINES.md).

`setup` is idempotent — run it again any time and it will only rebuild what is
missing. Requirements:

| dependency | used by | notes |
|---|---|---|
| Python 3.10+ | everything | the CLI itself |
| Node 18+ | Luraph, Prometheus, Ironveil, LuaObfuscator | no npm packages needed |
| .NET 8 SDK | 77fuscator, Moonsec | engines are compiled on setup |
| Luau runtime | layered VM engine, Centurion | downloaded automatically by `setup` |

Nothing else. No pip packages, no global installs.

---

## Usage

```text
deob <command> [args]

  list                     every engine, its target and whether it is ready
  detect <file>            fingerprint the file against all engines
  run <file>               detect and deobfuscate
  run <file> --all         run every engine, keep every dump
  run <file> -e <engine>   force one engine (repeatable)
  run <file> -o out.lua    copy the best result to a path
  setup                    fetch binaries + build .NET engines
  build                    rebuild the .NET engines only
  selftest                 smoke test each engine on its own samples
```

The `deob.bat` file is a one-line shortcut (`python deob.py %*`) so you can drop
it on `PATH` and forget the interpreter.

### Real runs

```console
$ deob detect pack.lua
pack.lua  (280360 bytes, 3 lines)
    6  luraph15   Luraph v15.x        ready  [luraph v15 banner, LPH marker]
    1  ferib      LuaObfuscator.com   ready  [VM shape: opcode table over bit32]
```

```console
$ deob run pack.lua -e hercules -o clean.lua -v
[run ] hercules -> Hercules 1.6.x - 2.0.1
    | [OK] pack.lua -> out/pack/hercules/pack_deobf.lua (decompiled, 3912 bytes)
[ ok ] hercules: 9828 bytes in 0.15s
wrote clean.lua  (from hercules, 9828 bytes)
```

```console
$ deob run unknown.lua --all --timeout 240
detected: nothing - brute forcing

  ok    layered                1471 bytes    0.9s
  part  luraph14               344 bytes    0.4s
  fail  centurion                0 bytes    0.1s
  fail  ferib                    0 bytes    2.9s
  ...
```

---

## Engines
## Engines

Thirteen engines, one interface. The `key` is what you pass to `-e`.

| # | key | protection | family | runtime | output |
|---|---|---|---|---|---|
| 01 | `luraph15` | Luraph v15.x | VM devirt | Node + Python | source |
| 02 | `luraph14` | Luraph v14.7 | VM devirt | Node + Python | source |
| 03 | `luraph_py` | Luraph 14.7 / 14.8 / 14.9 + IronBrew1 | VM devirt | Python | source |
| 04 | `ferib` | LuaObfuscator.com (Ferib) | symbolic lift | Python | IR to Lua |
| 05 | `prometheus` | Prometheus | interp + devirt | Node | source |
| 06 | `clyde` | Clyde V2 - V6 | static lift | Node | source |
| 07 | `hercules` | Hercules 1.6.x - 2.0.1 | decompiler | Python | decompiled / disasm |
| 08 | `ironveil` | Ironveil v1 | bytecode lift | Node | source |
| 09 | `luaobfuscator` | LuaObfuscator Chaotic Good / Evil | bytecode lift | Node | source |
| 10 | `fuscator77` | 77fuscator 0.6.x | VM to luac | .NET 8 | stock `.luac` chunk |
| 11 | `moonsec` | Moonsec v3 | bytecode rewriter | .NET 8 | source |
| 12 | `centurion` | Centurion / Luraph v6.x packs | static + sandbox | Python + Luau | lift, trace, maximal |
| 13 | `layered` | multi-layer Luau VM protectors | live constant recovery | Python + Luau | strings, pools, blobs |

`deob list` renders the same inventory live, with readiness per engine:

```text
+--------------------------------------------------------------+
| MULTI-DEOBFUSCATOR   13 engines   13 ready   0 missing       |
+--------------------------------------------------------------+
+---------------+----------------------------------+--------+---------+
| KEY           | TARGET                           | STACK  | STATUS  |
+---------------+----------------------------------+--------+---------+
| luraph15      | Luraph v15.x                     | node   | ready   |
| luraph14      | Luraph v14.7                     | node   | ready   |
| luraph_py     | Luraph 14.7 / 14.8 / 14.9        | py     | ready   |
| ferib         | LuaObfuscator.com (Ferib) VM     | py     | ready   |
| prometheus    | Prometheus                       | node   | ready   |
| clyde         | Clyde V2 - V6                    | node   | ready   |
| hercules      | Hercules 1.6.x - 2.0.1           | py     | ready   |
| ironveil      | Ironveil v1                      | node   | ready   |
| luaobfuscator | LuaObfuscator Chaotic Good/Evil  | node   | ready   |
| fuscator77    | 77fuscator 0.6.x                 | dotnet | ready   |
| moonsec       | Moonsec v3                       | dotnet | ready   |
| centurion     | Centurion / Luraph v6.x packs    | py     | ready   |
| layered       | multi-layer Luau VM protectors   | py     | ready   |
+---------------+----------------------------------+--------+---------+
```

`layered` is the one worth reading about: it does not guess the cipher, it runs
the loader and records every plaintext it produces. See
[docs/ENGINES.md](docs/ENGINES.md#layered).

---

## What "partial" means

A deobfuscator that lies to you is worse than one that fails.

| status | meaning |
|---|---|
| `ok` | exit 0 and a real file came out |
| `part` | something usable came out, but the engine flagged it incomplete — a trace-only fallback, a non-zero exit, or a stub far too small for the input |
| `fail` | no output, or the engine rejected the file |

Every run writes `_log.txt` with the exact command line, stdout, stderr and exit
code, plus `report.json` with per-engine results. If an engine says `part`, read
the log before you trust the dump.

---

## How detection works

Detection is static and cheap — no execution, no network:

1. every engine carries a set of markers: banners, blob headers, VM shapes,
   opcode-table signatures;
2. each marker hit scores the engine, with weighted hits for hard signatures
   (a Luraph banner is worth more than a generic dispatch table);
3. candidates are ordered by score, then by prior;
4. `run` walks the ordered list and stops at the first `ok`; `--all` keeps going
   and prints the size table so you can compare engines yourself.

No signature matched? It brute-forces the whole ladder instead of giving up.

---

## Architecture

```
deob.py            engine registry, detection, dispatch, result ranking
deob_live.py       layered-VM engine: instrumented replay in real Luau
tools/             helpers for generated sources (function/block extraction)
_engines/          engine sources, one directory per key
_build/            compiled .NET engines
_tools/luau/       luau.exe / luau-compile.exe / luau-ast.exe
out/<name>-<hash>/ per-input work dir: one folder per engine + report.json
```

Each run is isolated: `out/<stem>-<sha1>/<engine>/` holds that engine's output,
its log, and nothing else. Two files with the same name never collide.

Adding an engine is a dict entry — see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Layered VM recovery, in one paragraph

Some protectors ship as a single megabyte-long line: an alias header, a base-87
constant pool, a stream-cipher string decryptor and a VM whose payload is
Zstd-compressed at runtime. Instead of reversing the cipher, `deob_live` wraps
every `decrypt("<cipher>", seed)` call in a recorder, replays the loader inside
the real Luau runtime with authentic `buffer` and `bit32`, and dumps every value
the loader builds. You get the plaintext string table, the decoded pools, and
the binary payloads with an ASCII ratio and a bytecode flag — everything the
protector hands over before it starts checking whether it is running in Roblox.

```console
$ python deob_live.py target.lua --stubs
file      : target.lua
functions : 164 defined, 119 calls recorded
values    : 24
strings   : 15 unique plaintext
blobs     : 2 binary payloads
output    : out_live/target
```

---

## Troubleshooting

| symptom | fix |
|---|---|
| `engine not ready: not built` | `python deob.py build` |
| `dotnet not on PATH` | install the .NET 8 SDK, or skip the `fuscator77` / `moonsec` engines |
| `luau binaries missing` | `python deob.py setup` |
| engine exits non-zero with "not <obfuscator>" | wrong engine for that file — trust `deob detect`, or use `--all` |
| output is 0 bytes but exit 0 | the engine failed silently; that is what `part` is for — read `_log.txt` |
| a run hangs | pass `--timeout 120`; heavy devirtualisers legitimately take minutes |

---

## Issues and requests

This suite gets better from the scripts that break it. If an engine fails, a
detection misses, or an output comes back wrong — **open an issue and it gets
fixed**. If the obfuscator you are fighting is not in the table at all, **open an
engine request** and tell us which one you want next.

| what happened | where it goes |
|---|---|
| engine fails, output is garbage, CLI misbehaves | [Bug report](https://github.com/Pajt9whauht283as/MULTI-DEOBFUSCATOR/issues/new?template=bug_report.yml) |
| you want a new obfuscator supported | [Engine request](https://github.com/Pajt9whauht283as/MULTI-DEOBFUSCATOR/issues/new?template=engine_request.yml) |
| protection not detected at all | Bug report + the sample, that is enough |
| quick question, custom build | [Discord](https://discord.gg/Nkkq33F8GY), DM `broskie_king.` |

What makes a report land fast:

1. the engine key and the exact command you ran;
2. `out/<name>-<hash>/<engine>/_log.txt` and `report.json`;
3. the sample, or a smaller one that still reproduces it;
4. what you expected versus what came out.

Engine requests go on a board that is read in order, so the ones with a sample
attached move to the top. Nothing gets closed as "wontfix" without saying why.

---

## Community

Need an engine that is not in the table? Hit a protection this suite does not
know yet? Want a build tuned for your setup?

**Join the server: https://discord.gg/Nkkq33F8GY**

Inside, DM **`broskie_king.`** and say what you need — engine requests, samples
that break, tooling that we do not ship, custom builds. That is the fastest
route; issues on GitHub work too and are tracked properly, but the server gets
answered first.

```
discord  : https://discord.gg/Nkkq33F8GY
dm       : broskie_king.
```

---

## License

MIT. Do what you want with it.

<div align="center">

**If this saved you an afternoon, star it — that is how the next person finds it.**

</div>
