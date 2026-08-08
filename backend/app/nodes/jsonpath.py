"""jsonpath subset evaluator (SPEC §12: no third-party lib).

Supported: `$`, `.field`, `[0]`, `[*]`, `..field` — e.g. `$.shots[*].prompt`, `$..prompt`.
"""
from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"""
    (?P<recursive>\.\.)
  | (?P<dot>\.)
  | (?P<name>[A-Za-z_][\w\-]*)
  | \[(?P<index>\d+)\]
  | \[(?P<wildcard>\*)\]
""", re.VERBOSE)


class JsonPathError(ValueError):
    pass


def _tokenize(path: str) -> list[tuple[str, object]]:
    path = path.strip()
    if not path.startswith("$"):
        raise JsonPathError(f"jsonpath 必须以 $ 开头: {path!r}")
    pos = 1
    steps: list[tuple[str, object]] = []
    pending_recursive = False
    while pos < len(path):
        m = _TOKEN_RE.match(path, pos)
        if not m:
            raise JsonPathError(f"jsonpath 语法错误（位置 {pos}）: {path!r}")
        pos = m.end()
        if m.group("recursive") is not None:
            pending_recursive = True
            continue
        if m.group("dot") is not None:
            continue
        if m.group("index") is not None:
            if pending_recursive:
                raise JsonPathError("`..` 后只能跟字段名")
            steps.append(("index", int(m.group("index"))))
            continue
        if m.group("wildcard") is not None:
            if pending_recursive:
                raise JsonPathError("`..` 后只能跟字段名")
            steps.append(("wildcard", None))
            continue
        if m.group("name") is not None:
            steps.append(("recursive_field" if pending_recursive else "field", m.group("name")))
            pending_recursive = False
            continue
    if pending_recursive:
        raise JsonPathError(f"jsonpath 以 '..' 结尾: {path!r}")
    return steps


def _collect_recursive(value, name: str, out: list) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            if k == name:
                out.append(v)
            _collect_recursive(v, name, out)
    elif isinstance(value, list):
        for item in value:
            _collect_recursive(item, name, out)


def evaluate(data, path: str) -> list:
    """Evaluate jsonpath, returning a list of matched values."""
    current = [data]
    for kind, arg in _tokenize(path):
        nxt: list = []
        for value in current:
            if kind == "field":
                if isinstance(value, dict) and arg in value:
                    nxt.append(value[arg])
            elif kind == "index":
                if isinstance(value, list) and -len(value) <= arg < len(value):
                    nxt.append(value[arg])
            elif kind == "wildcard":
                if isinstance(value, list):
                    nxt.extend(value)
                elif isinstance(value, dict):
                    nxt.extend(value.values())
            elif kind == "recursive_field":
                _collect_recursive(value, arg, nxt)
        current = nxt
    return current
