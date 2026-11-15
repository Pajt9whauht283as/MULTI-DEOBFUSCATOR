# Architecture

Three layers: a registry, a runner, and the engines themselves. Nothing clever,
everything explicit.

```
             ┌──────────────┐
  file.lua → │  fingerprint │ → ranked engine list
             └──────────────┘
                    │
             ┌──────▼──────┐
             │   runner    │  per engine: fresh out dir, cwd, env, timeout
             └──────┬──────┘
                    │
       ┌────────────┼────────────┐
       ▼            ▼            ▼
   python        node          dotnet
       │            │            │
       └────────────┼────────────┘
                    ▼
        out/<stem>-<hash>/<engine>/
            result  _log.txt  report.json
```

## 1. Registry

`deob.py` holds one `Engine` record per engine:

```python
@dataclass
class Engine:
    key: str                     # -e value
    name: str
    target: str                  # what it deobfuscates, shown in `list`
    kind: str                    # py | node | dotnet
    root: str                    # directory under _engines/
    entry: str                   # entrypoint inside root
    args: list[str]              # {in} {out} {outdir} placeholders
    ext: str = ".lua"
    markers: list[(regex, label)]
    requires: tuple[str, ...]
    env: dict[str, str]
    fallback_args: list[str] | None
```

The registry is the single source of truth: `list`, `detect`, `run`, `build`,
`setup` and `selftest` all read from it. Adding an engine never touches the
runner.

## 2. Detection

`fingerprint(text)` scores every engine:

- each marker regex that matches adds a weighted score — hard signatures
  (banners, blob headers) score higher than structural guesses;
- repeated hits add a little, capped, so a giant file cannot win by volume;
- shape-only fallbacks catch stripped banners: an opcode table over
  `bit32`/`buffer`, an `LPH`-style constant marker, a generic dispatch table;
- results are ordered by score, then by the engine's prior.

`run` without `--all` walks that order and stops at the first `ok`. No match at
all means the whole ladder is tried in prior order.

## 3. Runner

For each engine:

1. `out/<stem>-<sha1(path)[:8]>/<engine>/` is created fresh, so two inputs with
   the same name never share a directory;
2. the command line is rendered from the template and the engine runs with
   `cwd` set to its own directory, its own env (used by Centurion to find the
   Luau binaries) and a hard timeout;
3. stdout and stderr go to `_log.txt` with the exact command line and exit code;
4. if the engine has `fallback_args`, a failed first attempt is retried once —
   this is how Luraph v14 gets a behaviour trace when full devirtualisation
   bails;
5. the primary artifact is picked: explicit `{out}` first, otherwise the best
   ranked file the engine produced.

## 4. Result states

```python
produced = primary is not None and primary.stat().st_size > 0
tiny     = produced and primary.stat().st_size < 64 and src.stat().st_size > 2048
ok       = produced and code == 0 and mode_used == "primary" and not tiny
status   = "ok" if ok else ("partial" if produced else "fail")
```

The `tiny` guard exists because several engines exit 0 with a 15-byte stub on a
200 KB input. That is a failure with better manners, and it is reported as
`partial`, never as `ok`.

## 5. Layered engine

`deob_live.py` is a different shape of engine: it does not transform the file,
it executes its loader and records what the loader builds. The interesting
details are in [ENGINES.md](ENGINES.md#layered).

The one non-obvious constraint: the target ends its chunk in a way that forbids
any further top-level statement, so instrumentation is attached *inside* call
expressions (`__rec(name, call)`) rather than appended after statements.

## 6. Filesystem

| path | purpose |
|---|---|
| `_engines/<key>/` | engine sources (not shipped) |
| `_build/<key>/` | compiled .NET engines |
| `_tools/luau/` | Luau toolchain, fetched by `setup` |
| `out/<stem>-<hash>/` | per-input work dir, one subfolder per engine |
| `out_live/<stem>/` | `deob_live` artifacts |
| `work/` | scratch: generated harness sources |

`out/`, `_build/`, `_tools/` and `work/` are all disposable. `_engines/` is the
only thing you would back up.
