"""DAG construction, topo sort, cycle detection, validation (SPEC §5.5 dag.py)."""
from __future__ import annotations

from collections import defaultdict, deque

from ..nodes.base import NODE_REGISTRY
from ..nodes.types import types_compatible


class WorkflowValidationError(ValueError):
    pass


def build_graph(nodes: list[dict], edges: list[dict]) -> dict[str, list[str]]:
    """Adjacency list: node_id -> [downstream node_ids]."""
    adj: dict[str, list[str]] = {n["id"]: [] for n in nodes}
    for e in edges:
        adj.setdefault(e["source"], []).append(e["target"])
        adj.setdefault(e["target"], adj.get(e["target"], []))
    return adj


def reverse_graph(nodes: list[dict], edges: list[dict]) -> dict[str, list[str]]:
    rev: dict[str, list[str]] = {n["id"]: [] for n in nodes}
    for e in edges:
        rev.setdefault(e["target"], []).append(e["source"])
    return rev


def topological_sort(nodes: list[dict], edges: list[dict]) -> list[str]:
    """Kahn's algorithm. Raises WorkflowValidationError on cycle."""
    node_ids = [n["id"] for n in nodes]
    adj = build_graph(nodes, edges)
    in_degree = {nid: 0 for nid in node_ids}
    for e in edges:
        if e["target"] in in_degree:
            in_degree[e["target"]] += 1
    queue = deque([nid for nid in node_ids if in_degree[nid] == 0])
    order: list[str] = []
    while queue:
        nid = queue.popleft()
        order.append(nid)
        for nxt in adj.get(nid, []):
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)
    if len(order) != len(node_ids):
        raise WorkflowValidationError("工作流存在环（cycle），无法拓扑排序")
    return order


def topo_layers(nodes: list[dict], edges: list[dict]) -> list[list[str]]:
    """Kahn by level: nodes in the same layer have no mutual dependencies."""
    layers, _rev, _adj = analyze(nodes, edges)
    return layers


def analyze(nodes: list[dict], edges: list[dict]) -> tuple[list[list[str]], dict[str, list[str]], dict[str, list[str]]]:
    """One-pass DAG analysis: returns (topo_layers, reverse_adjacency, adjacency).

    Builds both adjacency maps and the layer order in a single traversal — the engine's
    hot path previously rebuilt each structure separately on every run.
    """
    node_ids = [n["id"] for n in nodes]
    adj: dict[str, list[str]] = {nid: [] for nid in node_ids}
    rev: dict[str, list[str]] = {nid: [] for nid in node_ids}
    in_degree = {nid: 0 for nid in node_ids}
    for e in edges:
        adj.setdefault(e["source"], []).append(e["target"])
        rev.setdefault(e["target"], []).append(e["source"])
        if e["target"] in in_degree:
            in_degree[e["target"]] += 1
    current = [nid for nid in node_ids if in_degree[nid] == 0]
    layers: list[list[str]] = []
    done = 0
    while current:
        layers.append(current)
        done += len(current)
        nxt: list[str] = []
        for nid in current:
            for m in adj.get(nid, []):
                in_degree[m] -= 1
                if in_degree[m] == 0:
                    nxt.append(m)
        current = nxt
    if done != len(node_ids):
        raise WorkflowValidationError("工作流存在环（cycle），无法拓扑排序")
    return layers, rev, adj


def detect_cycle(nodes: list[dict], edges: list[dict]) -> bool:
    try:
        topological_sort(nodes, edges)
        return False
    except WorkflowValidationError:
        return True


def ancestors(nodes: list[dict], edges: list[dict], node_id: str) -> set[str]:
    rev = reverse_graph(nodes, edges)
    seen: set[str] = set()
    stack = [node_id]
    while stack:
        cur = stack.pop()
        for up in rev.get(cur, []):
            if up not in seen:
                seen.add(up)
                stack.append(up)
    return seen


def descendants(nodes: list[dict], edges: list[dict], node_id: str) -> set[str]:
    adj = build_graph(nodes, edges)
    seen: set[str] = set()
    stack = [node_id]
    while stack:
        cur = stack.pop()
        for down in adj.get(cur, []):
            if down not in seen:
                seen.add(down)
                stack.append(down)
    return seen


def validate(nodes: list[dict], edges: list[dict]) -> None:
    """SPEC §5.5: unknown node types, unknown node ids, missing required inputs,
    port type incompatibility (§2), duplicate edges into a single (non-multiple) input."""
    node_by_id = {n["id"]: n for n in nodes}
    errors: list[str] = []

    for n in nodes:
        if NODE_REGISTRY.get(n.get("type", "")) is None:
            errors.append(f"未知节点类型: {n.get('type')} (node {n.get('id')})")

    for e in edges:
        if e.get("source") not in node_by_id:
            errors.append(f"边 {e.get('id')} 引用了不存在的 source 节点 {e.get('source')}")
        if e.get("target") not in node_by_id:
            errors.append(f"边 {e.get('id')} 引用了不存在的 target 节点 {e.get('target')}")

    if errors:
        raise WorkflowValidationError("; ".join(errors))

    incoming: dict[str, list[dict]] = defaultdict(list)
    for e in edges:
        src_node = node_by_id[e["source"]]
        tgt_node = node_by_id[e["target"]]
        src_cls = NODE_REGISTRY.get(src_node["type"])
        tgt_cls = NODE_REGISTRY.get(tgt_node["type"])
        if src_cls is None or tgt_cls is None:
            continue
        out_port = next((p for p in src_cls.outputs if p.key == e.get("source_handle")), None)
        in_port = next((p for p in tgt_cls.inputs if p.key == e.get("target_handle")), None)
        if out_port is None:
            errors.append(f"节点 {e['source']} 没有输出端口 {e.get('source_handle')}")
            continue
        if in_port is None:
            errors.append(f"节点 {e['target']} 没有输入端口 {e.get('target_handle')}")
            continue
        if not types_compatible(out_port.type, in_port.type):
            errors.append(
                f"端口类型不兼容: {src_node['type']}.{out_port.key}({out_port.type}) -> "
                f"{tgt_node['type']}.{in_port.key}({in_port.type})"
            )
        incoming[e["target"]].append((e, in_port))

    for nid, pairs in incoming.items():
        singles: dict[str, int] = defaultdict(int)
        for e, port in pairs:
            if not port.multiple:
                singles[port.key] += 1
        for key, count in singles.items():
            if count > 1:
                errors.append(f"节点 {nid} 的单输入端口 {key} 被连接了 {count} 次")

    for n in nodes:
        cls = NODE_REGISTRY.get(n["type"])
        if cls is None:
            continue
        connected = {e["target_handle"] for e in edges if e["target"] == n["id"]}
        for port in cls.inputs:
            if port.required and port.key not in connected:
                errors.append(f"节点 {n['id']} ({n['type']}) 缺少必填输入 {port.key}")

    if detect_cycle(nodes, edges):
        errors.append("工作流存在环（cycle）")

    if errors:
        raise WorkflowValidationError("; ".join(errors))
