// Infinite canvas (SPEC §10): @xyflow/react only — no custom canvas/edge system.
import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  useReactFlow,
  type Edge,
  type NodeTypes,
} from '@xyflow/react';
import { useCallback, useEffect, useState, type DragEvent, type MouseEvent } from 'react';
import SchemaNode from '../nodes/SchemaNode';
import { useUIStore } from '../stores/uiStore';
import { useWorkflowStore } from '../stores/workflowStore';
import { EmptyCanvasGuide } from '../components/EmptyCanvasGuide';
import { NodeContextMenu } from './NodeContextMenu';
import { NodeSearch } from './NodeSearch';
import { useShortcuts } from './useShortcuts';

const nodeTypes: NodeTypes = { schemaNode: SchemaNode };

interface MenuState {
  x: number;
  y: number;
  nodeId: string;
}

export function Canvas() {
  const nodes = useWorkflowStore((s) => s.nodes);
  const edges = useWorkflowStore((s) => s.edges);
  const onNodesChange = useWorkflowStore((s) => s.onNodesChange);
  const onEdgesChange = useWorkflowStore((s) => s.onEdgesChange);
  const onConnect = useWorkflowStore((s) => s.onConnect);
  const isValidConnection = useWorkflowStore((s) => s.isValidConnection);
  const addNode = useWorkflowStore((s) => s.addNode);
  const viewport = useWorkflowStore((s) => s.viewport);
  const setViewport = useWorkflowStore((s) => s.setViewport);
  const workflowId = useWorkflowStore((s) => s.workflowId);
  const openNodeSearch = useUIStore((s) => s.openNodeSearch);

  const { screenToFlowPosition, fitView } = useReactFlow();
  const [menu, setMenu] = useState<MenuState | null>(null);

  useShortcuts();

  // 切换/恢复工作流后自动 Fit View：节点永远在视野内，
  // 避免 defaultViewport 只在挂载时生效导致的"打开后看不到节点"。
  useEffect(() => {
    if (!workflowId) return;
    const t = setTimeout(() => {
      void fitView({ padding: 0.2, duration: 200 });
    }, 80);
    return () => clearTimeout(t);
  }, [workflowId, fitView]);

  const onDragOver = useCallback((e: DragEvent) => {
    if (e.dataTransfer.types.includes('application/aivwf-node')) {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
    }
  }, []);

  const onDrop = useCallback(
    (e: DragEvent) => {
      const nodeType = e.dataTransfer.getData('application/aivwf-node');
      if (!nodeType) return;
      e.preventDefault();
      addNode(nodeType, screenToFlowPosition({ x: e.clientX, y: e.clientY }));
    },
    [addNode, screenToFlowPosition],
  );

  const onNodeContextMenu = useCallback((e: MouseEvent, node: { id: string }) => {
    e.preventDefault();
    setMenu({ x: e.clientX, y: e.clientY, nodeId: node.id });
  }, []);

  const onDoubleClick = useCallback(
    (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target.closest('.react-flow__pane') && !target.closest('.react-flow__node')) {
        openNodeSearch(
          screenToFlowPosition({ x: e.clientX, y: e.clientY }).x,
          screenToFlowPosition({ x: e.clientX, y: e.clientY }).y,
        );
      }
    },
    [openNodeSearch, screenToFlowPosition],
  );

  return (
    <div className="relative min-h-0 flex-1">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        isValidConnection={isValidConnection}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onNodeContextMenu={onNodeContextMenu}
        onDoubleClick={onDoubleClick}
        onMoveEnd={(_, vp) => setViewport(vp)}
        defaultViewport={viewport}
        minZoom={0.2}
        maxZoom={2.5}
        connectionRadius={30}
        selectionOnDrag
        panOnDrag={[1, 2]}
        deleteKeyCode={null}
        fitViewOptions={{ padding: 0.2 }}
        proOptions={{ hideAttribution: false }}
        colorMode="dark"
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#27272a" />
        <Controls position="bottom-left" />
        <MiniMap
          position="bottom-right"
          pannable
          zoomable
          nodeColor="#3f3f46"
          maskColor="rgba(9, 9, 11, 0.7)"
        />
      </ReactFlow>

      <NodeSearch />
      <NodeContextMenu menu={menu} onClose={() => setMenu(null)} />
      {nodes.length === 0 ? <EmptyCanvasGuide /> : null}
    </div>
  );
}

export type { Edge };
