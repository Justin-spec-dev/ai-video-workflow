// 节点右键菜单（§10）：运行节点 / 从此节点运行 / 重试 / 清除缓存 / 查看输入 / 查看输出 / 删除。
import { Eraser, Eye, Play, PlayCircle, RotateCcw, Trash2 } from 'lucide-react';
import * as api from '../api/resources';
import { ApiError } from '../api/client';
import { ContextMenu, ContextMenuItem, ContextMenuSeparator } from '../components/ui/context-menu';
import { toast } from '../components/ui/toast';
import { useUIStore } from '../stores/uiStore';
import { useWorkflowStore } from '../stores/workflowStore';

interface Props {
  menu: { x: number; y: number; nodeId: string } | null;
  onClose: () => void;
}

export function NodeContextMenu({ menu, onClose }: Props) {
  const workflowId = useWorkflowStore((s) => s.workflowId);
  const openInspect = useUIStore((s) => s.openInspect);

  if (!menu) return null;
  const { nodeId } = menu;

  const guard = async (action: () => Promise<unknown>, okMessage: string) => {
    if (!workflowId) return;
    try {
      await action();
      toast.success(okMessage);
    } catch (e) {
      const msg = e instanceof ApiError ? e.detail : e instanceof Error ? e.message : '请求失败';
      toast.error('操作失败', msg);
    }
  };

  return (
    <ContextMenu state={menu} onClose={onClose}>
      <ContextMenuItem onClick={() => void guard(() => api.runNode(workflowId!, nodeId, false), '已开始运行该节点')}>
        <Play size={13} /> 运行节点
      </ContextMenuItem>
      <ContextMenuItem onClick={() => void guard(() => api.runNode(workflowId!, nodeId, true), '已从该节点开始运行')}>
        <PlayCircle size={13} /> 从此节点运行
      </ContextMenuItem>
      <ContextMenuItem onClick={() => void guard(() => api.runNode(workflowId!, nodeId, false), '已开始重试')}>
        <RotateCcw size={13} /> 重试
      </ContextMenuItem>
      <ContextMenuItem onClick={() => void guard(() => api.clearNodeCache(workflowId!, nodeId), '缓存已清除')}>
        <Eraser size={13} /> 清除缓存
      </ContextMenuItem>
      <ContextMenuSeparator />
      <ContextMenuItem onClick={() => openInspect(nodeId, 'input')}>
        <Eye size={13} /> 查看输入
      </ContextMenuItem>
      <ContextMenuItem onClick={() => openInspect(nodeId, 'output')}>
        <Eye size={13} /> 查看输出
      </ContextMenuItem>
      <ContextMenuSeparator />
      <ContextMenuItem
        danger
        onClick={() => useWorkflowStore.getState().onNodesChange([{ type: 'remove', id: nodeId }])}
      >
        <Trash2 size={13} /> 删除
      </ContextMenuItem>
    </ContextMenu>
  );
}
