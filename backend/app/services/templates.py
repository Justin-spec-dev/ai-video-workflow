"""Built-in workflow templates (SPEC §8). Returned as §4 workflow JSON."""
from __future__ import annotations


def _node(nid: str, type_: str, x: int, y: int, config: dict | None = None) -> dict:
    return {"id": nid, "type": type_, "position": {"x": x, "y": y}, "config": config or {}}


def _edge(eid: str, source: str, sh: str, target: str, th: str) -> dict:
    return {"id": eid, "source": source, "source_handle": sh, "target": target, "target_handle": th}


def _wf(name: str, nodes: list[dict], edges: list[dict]) -> dict:
    return {"version": 1, "name": name, "nodes": nodes, "edges": edges,
            "viewport": {"x": 0, "y": 0, "zoom": 1}}


TEMPLATES: dict[str, dict] = {
    "text_to_video": _wf(
        "Text to Video",
        [
            _node("n1", "prompt", 0, 0),
            _node("n2", "prompt_optimizer", 320, 0),
            _node("n3", "video_generation", 680, 0),
            _node("n4", "video_preview", 1040, 0),
        ],
        [
            _edge("e1", "n1", "prompt", "n2", "prompt"),
            _edge("e2", "n2", "prompt", "n3", "prompt"),
            _edge("e3", "n3", "video", "n4", "video"),
        ],
    ),
    "image_to_video": _wf(
        "Image to Video",
        [
            _node("n1", "image_input", 0, 0),
            _node("n2", "prompt", 0, 220),
            _node("n3", "video_generation", 360, 100),
            _node("n4", "video_preview", 720, 100),
        ],
        [
            _edge("e1", "n1", "image", "n3", "image"),
            _edge("e2", "n2", "prompt", "n3", "prompt"),
            _edge("e3", "n3", "video", "n4", "video"),
        ],
    ),
    "last_frame_continue": _wf(
        "Last Frame Continue",
        [
            _node("n1", "prompt", 0, 0),
            _node("n2", "prompt_optimizer", 300, 0),
            _node("n3", "video_generation", 640, 0),
            _node("n4", "last_frame", 980, 0),
            _node("n5", "prompt", 300, 260),
            _node("n6", "prompt_optimizer", 640, 260),
            _node("n7", "video_generation", 980, 200),
            _node("n8", "video_preview", 1320, 0),
            _node("n9", "video_preview", 1320, 200),
        ],
        [
            _edge("e1", "n1", "prompt", "n2", "prompt"),
            _edge("e2", "n2", "prompt", "n3", "prompt"),
            _edge("e3", "n3", "video", "n4", "video"),
            _edge("e4", "n4", "image", "n7", "image"),
            _edge("e5", "n5", "prompt", "n6", "prompt"),
            _edge("e6", "n6", "prompt", "n7", "prompt"),
            _edge("e7", "n3", "video", "n8", "video"),
            _edge("e8", "n7", "video", "n9", "video"),
        ],
    ),
    "three_shot_movie": _wf(
        "Three Shot Movie",
        [
            _node("p1", "prompt", 0, 0), _node("o1", "prompt_optimizer", 280, 0),
            _node("v1", "video_generation", 600, 0),
            _node("p2", "prompt", 0, 220), _node("o2", "prompt_optimizer", 280, 220),
            _node("v2", "video_generation", 600, 220),
            _node("p3", "prompt", 0, 440), _node("o3", "prompt_optimizer", 280, 440),
            _node("v3", "video_generation", 600, 440),
            _node("m", "video_merge", 940, 220),
            _node("pv", "video_preview", 1280, 220),
        ],
        [
            _edge("e1", "p1", "prompt", "o1", "prompt"), _edge("e2", "o1", "prompt", "v1", "prompt"),
            _edge("e3", "p2", "prompt", "o2", "prompt"), _edge("e4", "o2", "prompt", "v2", "prompt"),
            _edge("e5", "p3", "prompt", "o3", "prompt"), _edge("e6", "o3", "prompt", "v3", "prompt"),
            _edge("e7", "v1", "video", "m", "videos"),
            _edge("e8", "v2", "video", "m", "videos"),
            _edge("e9", "v3", "video", "m", "videos"),
            _edge("e10", "m", "video", "pv", "video"),
        ],
    ),
    "story_to_storyboard": _wf(
        "Story to Storyboard",
        [
            _node("n1", "text", 0, 0),
            _node("n2", "llm", 320, 0),
            _node("n3", "storyboard", 660, 0),
        ],
        [
            _edge("e1", "n1", "text", "n2", "prompt"),
            _edge("e2", "n2", "text", "n3", "story"),
        ],
    ),
}


def list_templates() -> list[dict]:
    return [{"id": key, "name": tpl["name"], "data": tpl} for key, tpl in TEMPLATES.items()]
