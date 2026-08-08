import type { PortType } from '../types';
import { isArrayPort, portBase } from '../workflow/validation';

/** Handle colors per SPEC §10: TEXT 灰 / PROMPT 蓝 / IMAGE 绿 / VIDEO 紫 / JSON 黄 / … */
const BASE_COLORS: Record<string, string> = {
  TEXT: '#a1a1aa', // zinc-400
  PROMPT: '#60a5fa', // blue-400
  IMAGE: '#4ade80', // green-400
  VIDEO: '#c084fc', // purple-400
  AUDIO: '#f472b6', // pink-400
  JSON: '#facc15', // yellow-400
  NUMBER: '#fb923c', // orange-400
  BOOLEAN: '#f87171', // red-400
  FILE: '#22d3ee', // cyan-400
};

export function portColor(type: PortType): string {
  return BASE_COLORS[portBase(type)] ?? '#71717a';
}

/** Array ports get a ring around the filled handle. */
export function portHandleStyle(type: PortType): React.CSSProperties {
  const color = portColor(type);
  if (isArrayPort(type)) {
    return { background: '#09090b', border: `2px solid ${color}`, boxShadow: `inset 0 0 0 2px ${color}` };
  }
  return { background: color, border: '2px solid #09090b' };
}
