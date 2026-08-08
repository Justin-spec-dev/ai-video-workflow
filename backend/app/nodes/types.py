"""PortType system (SPEC §2)."""
from __future__ import annotations

TEXT = "TEXT"
PROMPT = "PROMPT"
IMAGE = "IMAGE"
VIDEO = "VIDEO"
AUDIO = "AUDIO"
JSON = "JSON"
NUMBER = "NUMBER"
BOOLEAN = "BOOLEAN"
FILE = "FILE"

BASE_TYPES = {TEXT, PROMPT, IMAGE, VIDEO, AUDIO, JSON, NUMBER, BOOLEAN, FILE}
ARRAY_TYPES = {"TEXT[]", "PROMPT[]", "IMAGE[]", "VIDEO[]", "JSON[]"}


def is_array(t: str) -> bool:
    return t.endswith("[]")


def base_of(t: str) -> str:
    return t[:-2] if is_array(t) else t


def _scalar_compatible(src: str, dst: str) -> bool:
    if src == dst:
        return True
    # PROMPT <-> TEXT are interchangeable
    if {src, dst} == {TEXT, PROMPT}:
        return True
    return False


def types_compatible(src: str, dst: str) -> bool:
    """Whether an output port of type `src` may connect into an input port of type `dst`."""
    if is_array(src) or is_array(dst):
        # VIDEO output may feed a VIDEO[] (multiple) input
        if not is_array(src) and is_array(dst):
            return _scalar_compatible(src, base_of(dst))
        if is_array(src) and is_array(dst):
            return _scalar_compatible(base_of(src), base_of(dst))
        return False
    return _scalar_compatible(src, dst)
