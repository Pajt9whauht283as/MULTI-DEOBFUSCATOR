# --discord.gg/Nkkq33F8GY--
"""Extract a Lua function definition from source text by matching block ends.

`for`/`while` open their block through their trailing `do`, so only
function/if/do/repeat count as openers. Strings and comments are skipped.
"""
from __future__ import annotations


def tokens(src: str, start: int = 0):
    """Yield (kind, text, start, end) for every token."""
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


OPENERS = {"function", "if", "do", "repeat"}
CLOSERS = {"end", "until"}


def block_end(src: str, open_pos: int) -> int:
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


def find_function(src: str, name: str) -> tuple[int, int] | None:
    at = src.find(f"function {name}(")
    if at < 0:
        return None
    start = at
    head = src.rfind("local", max(0, at - 12), at)
    if head >= 0 and src[head:at].strip() == "local":
        start = head
    end = block_end(src, at)
    return (start, end) if end > 0 else None


def find_call_literal(src: str, fn: str, occurrence: int = 0) -> tuple[str, int] | None:
    """Return (literal body, offset) for the Nth direct string argument to fn."""
    seen = 0
    i = 0
    while True:
        at = src.find(f"{fn}(", i)
        if at < 0:
            return None
        j = at + len(fn) + 1
        while j < len(src) and src[j] in " \t\n":
            j += 1
        if j < len(src) and src[j] in "\"'":
            q = src[j]
            k = j + 1
            while k < len(src):
                if src[k] == "\\":
                    k += 2
                    continue
                if src[k] == q:
                    break
                k += 1
            if seen == occurrence:
                return src[j + 1:k], j
            seen += 1
        i = at + len(fn)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    src = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
    name = sys.argv[2]
    span = find_function(src, name)
    print("span", span, "len", (span[1] - span[0]) if span else 0)
    if span:
        print(src[span[0]:span[1]][:1500])
