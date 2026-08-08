"""BaseNode, PortDef, ConfigField, NodeRegistry (SPEC §5.1 / §3)."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import BaseModel

if TYPE_CHECKING:
    from ..workflow.context import ExecutionContext


class PortDef(BaseModel):
    key: str
    name: str
    type: str
    required: bool = False
    multiple: bool = False
    description: str = ""


class ConfigField(BaseModel):
    key: str
    name: str
    # text | textarea | number | boolean | select | credential | model | json | file | slider
    type: str
    default: Any = None
    description: str = ""
    placeholder: str | None = None
    options: list[str] | None = None
    provider_kind: str | None = None  # for type=credential
    min: float | None = None
    max: float | None = None
    step: float | None = None
    rows: int | None = None

    def model_dump(self, **kwargs):  # drop None values to keep schema compact
        data = super().model_dump(**kwargs)
        return {k: v for k, v in data.items() if v is not None}


class BaseNode:
    type: ClassVar[str] = ""
    name: ClassVar[str] = ""
    version: ClassVar[str] = "1.0.0"
    category: ClassVar[str] = "Utility"
    description: ClassVar[str] = ""
    is_paid: ClassVar[bool] = False
    #: 变量注入型节点（如 Variables）在主层循环前先执行，保证 {{var}} 确定性解析
    provides_variables: ClassVar[bool] = False
    inputs: ClassVar[list[PortDef]] = []
    outputs: ClassVar[list[PortDef]] = []
    config_schema: ClassVar[list[ConfigField]] = []

    async def execute(self, inputs: dict, config: dict, context: "ExecutionContext") -> dict:
        raise NotImplementedError

    @classmethod
    def schema(cls) -> dict:
        return {
            "type": cls.type,
            "name": cls.name,
            "version": cls.version,
            "category": cls.category,
            "description": cls.description,
            "is_paid": cls.is_paid,
            "inputs": [p.model_dump() for p in cls.inputs],
            "outputs": [p.model_dump(exclude={"required", "multiple", "description"}) for p in cls.outputs],
            "config_schema": [c.model_dump() for c in cls.config_schema],
        }


class NodeRegistry:
    def __init__(self) -> None:
        self._nodes: dict[str, type[BaseNode]] = {}

    def register(self, cls: type[BaseNode]) -> type[BaseNode]:
        if not cls.type:
            raise ValueError(f"Node class {cls.__name__} missing 'type'")
        self._nodes[cls.type] = cls
        return cls

    def get(self, type_: str) -> type[BaseNode] | None:
        return self._nodes.get(type_)

    def all(self) -> dict[str, type[BaseNode]]:
        return dict(self._nodes)

    def all_schemas(self) -> list[dict]:
        return [cls.schema() for cls in self._nodes.values()]


NODE_REGISTRY = NodeRegistry()


def register_node(cls: type[BaseNode]) -> type[BaseNode]:
    return NODE_REGISTRY.register(cls)
