import type { Node } from '@xyflow/react';

/** React Flow node data for the schema-driven custom node. */
export interface SchemaNodeData extends Record<string, unknown> {
  /** The backend node type id (SPEC §3 `type`). */
  nodeType: string;
  /** Instance config values keyed by config_schema key. Never contains secrets. */
  config: Record<string, unknown>;
}

export type SchemaFlowNode = Node<SchemaNodeData, 'schemaNode'>;
