# Engines

Every engine is a directory under `_engines/`. The key is what you pass to
`-e`, and the layout is what `deob.py` expects. If a directory is missing the
engine simply reports `source missing` — the rest of the suite keeps working.

## Layout

```
_engines/
  <key>/
    <entrypoint>
```

| key | expected entrypoint | stack |
|---|---|---|
| `luraph15` | `deob.js` | Node + Python bridge |
| `luraph14` | `deob.js` | Node + Python bridge |
| `luraph_py` | `cli.py` | Python |
| `ferib` | `deobfuscate.py` | Python |
| `prometheus` | `bin/pdeobf.js` | Node |
| `clyde` | `cli.js` | Node |
| `hercules` | `deobfhercules.py` | Python |
| `ironveil` | `index.js` | Node |
| `luaobfuscator` | `index.js` | Node |
| `fuscator77` | `deobfuscator.csproj` | .NET 8 |
| `moonsec` | `MoonsecDeobfuscator.csproj` | .NET 8 |
| `centurion` | `centurion.py` | Python + Luau |
| `layered` | *(built in)* | Python + Luau |

Sub-paths inside an engine directory are configured in the `root` field of the
registry in `deob.py`; adjust them if your copy nests differently.

## Invocation contract

`deob.py` builds the command line from the engine's `args` template:

| placeholder | replaced with |
|---|---|
| `{in}` | absolute path to the input file |
| `{out}` | path where the engine should write its primary result |
| `{outdir}` | a fresh per-run directory the engine may fill with anything |

The engine runs with `cwd` set to its own directory, so relative paths inside an
engine keep working. Stdout and stderr are captured verbatim into `_log.txt`.

## Result selection

Engines that write `{out}` are trusted directly. Engines that write many files
(Centurion, for example) are ranked: `*.lua` / `*.luac` wins over other text,
tokens like `clean`, `beautified`, `maximal`, `reconstructed` add weight, and
tokens like `harness`, `.trace.`, `.raw`, `_index` are treated as side artifacts.

## `layered`

`deob_live.py` targets protectors that ship as one enormous line:

```
local a=rawset local b=game local c=bit32 ...
<a base-N constant pool decoder>
<a stream-cipher string decryptor>
<a Luau VM whose payload is Zstd-compressed at runtime>
```

It does not reverse the cipher. It instruments it:

1. every `local function NAME(` is located, and every call of the form
   `NAME("<long literal>", ...)` is rewritten to `__rec("NAME", NAME(...))`;
2. the whole source is replayed inside the real Luau runtime, so `buffer`,
   `bit32` and the arithmetic behave exactly as they do in Roblox;
3. `--stubs` installs permissive stand-ins for `game`, `Enum`, the datatypes and
   `task`, which is enough to walk past the loader's environment checks;
4. every recorded value is dumped: strings as hex, buffers as hex, tables as
   their entry count.

Output, under `out_live/<name>/`:

| file | content |
|---|---|
| `strings.txt` | plaintext per recorded call, one `name<TAB>value` per line |
| `recovered_strings.lua` | the same strings as a Lua table you can require |
| `values.txt` | every value with type and 120-char preview |
| `blobs/*.bin` | binary payloads plus `blobs.json` with ASCII ratio and bytecode flag |
| `report.json` | functions instrumented, calls recorded, where the replay stopped |

Add `--no-blobs` when you only care about the text, and `--timeout` when a load
phase is slow.

## Adding an engine

```python
_add(Engine(
    key="myengine",
    name="My Engine",
    target="MyObfuscator v2",
    kind="node",                       # py | node | dotnet
    root="myengine",                   # directory under _engines/
    entry="cli.js",                    # entrypoint inside it
    args=["{in}", "-o", "{out}"],      # {in} {out} {outdir}
    markers=[
        (r"--\s*protected by MyObfuscator", "banner"),
        (r"MyVM\[opcodes\]", "vm shape"),
    ],
))
```

That is the whole integration. Detection, ordering, logging, result ranking and
the `--all` table come for free.
