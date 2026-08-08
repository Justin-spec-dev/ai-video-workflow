// SPEC §2 connection compatibility rules, enforced client-side on connect.
import type { Connection, Edge } from '@xyflow/react';
import type { NodeSchema, PortDef, PortType } from '../types';
import type { SchemaFlowNode } from '../types/rf';

export function isArrayPort(t: PortType): boolean {
  return t.endsWith('[]');
}

export function portBase(t: PortType): string {
  return isArrayPort(t) ? t.slice(0, -2) : t;
}

/** Base-type compatibility: identical, or PROMPT<->TEXT in either direction. */
export function isBaseCompatible(source: string, target: string): boolean {
  if (source === target) return true;
  if (source === 'PROMPT' && target === 'TEXT') return true;
  if (source === 'TEXT' && target === 'PROMPT') return true;
  return false;
}

/**
 * Port compatibility (SPEC §2):
 * - identical types allowed;
 * - PROMPT <-> TEXT allowed;
 * - arrays only compatible with arrays of a compatible base;
 * - a scalar output may feed an array input (e.g. VIDEO -> VIDEO[] on Video Merge);
 * - everything else forbidden (notably VIDEO -> PROMPT).
 */
export function isPortCompatible(source: PortType, target: PortType): boolean {
  const srcArr = isArrayPort(source);
  const tgtArr = isArrayPort(target);
  if (srcArr && !tgtArr) return false;
  // scalar -> array allowed (array input collects multiple scalars);
  // array -> array checked by base below.
  return isBaseCompatible(portBase(source), portBase(target));
}

export interface ConnectionCheck {
  ok: boolean;
  reason?: string;
}

function findPort(ports: PortDef[], key: string | null | undefined): PortDef | undefined {
  if (!key) return undefined;
  return ports.find((p) => p.key === key);
}

/** Full validation of a pending connection against graph state. */
export function validateConnection(
  conn: Connection | Edge,
  nodes: SchemaFlowNode[],
  edges: Edge[],
  schemas: Record<string, NodeSchema>,
): ConnectionCheck {
  if (!conn.source || !conn.target) return { ok: false, reason: '连接不完整' };
  if (conn.source === conn.target) return { ok: false, reason: '节点不能连接自身' };

  const sourceNode = nodes.find((n) => n.id === conn.source);
  const targetNode = nodes.find((n) => n.id === conn.target);
  if (!sourceNode || !targetNode) return { ok: false, reason: '未知节点' };

  const sourceSchema = schemas[sourceNode.data.nodeType];
  const targetSchema = schemas[targetNode.data.nodeType];
  if (!sourceSchema || !targetSchema) return { ok: false, reason: '未知节点类型' };

  const outPort = findPort(sourceSchema.outputs, conn.sourceHandle);
  const inPort = findPort(targetSchema.inputs, conn.targetHandle);
  if (!outPort || !inPort) return { ok: false, reason: '未知端口' };

  if (!isPortCompatible(outPort.type, inPort.type)) {
    return {
      ok: false,
      reason: `端口类型不兼容：${outPort.type} → ${inPort.type}`,
    };
  }

  // Single-input ports accept exactly one incoming edge; multiple (e.g. VIDEO[]) accept many.
  const existing = edges.some(
    (e) => e.target === conn.target && e.targetHandle === conn.targetHandle,
  );
  if (existing && !inPort.multiple) {
    return { ok: false, reason: `输入端口「${inPort.name}」已有连接` };
  }
  if (existing && inPort.multiple) {
    const dup = edges.some(
      (e) =>
        e.target === conn.target &&
        e.targetHandle === conn.targetHandle &&
        e.source === conn.source &&
        e.sourceHandle === conn.sourceHandle,
    );
    if (dup) return { ok: false, reason: '重复连接' };
  }

  return { ok: true };
}
