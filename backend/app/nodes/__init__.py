"""Node package: importing this module registers all built-in nodes (SPEC §5.1)."""
from . import context_nodes, image, output, text, video  # noqa: F401
from . import ai, json_parser  # noqa: F401
from .base import NODE_REGISTRY, BaseNode, NodeRegistry, PortDef, ConfigField, register_node  # noqa: F401
