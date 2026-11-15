# Contributing

Adding an engine is the most useful thing you can send. It is a single dict entry
in `deob.py` — see [docs/ENGINES.md](docs/ENGINES.md#adding-an-engine).

## Rules

- **Never report a false `ok`.** If an engine exits 0 with a stub, that is
  `partial`. The status field is the whole product.
- **One engine, one directory.** No shared state between engines, no assumptions
  about the other eleven.
- **Log everything.** A run that fails without a readable `_log.txt` is a bug.
- **No network at run time.** Detection and deobfuscation are local. `setup` may
  download binaries; `run` may not.

## Testing an engine

```bash
python deob.py list                  # is it ready?
python deob.py selftest              # bundled samples, per engine
python deob.py run sample.lua -e yourkey -v
```

`selftest` expects `ok` or `partial` for every engine that has a bundled sample;
a `fail` there is a regression.

## Style

Python: stdlib only, no dependencies, dataclasses over dicts, errors reported
rather than raised at the CLI boundary. Comments explain *why*, never *what*.
