import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
  type NodeProps,
  useNodesState,
  useEdgesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import PromptDetail from "./PromptDetail";

interface TreeNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: {
    label: string;
    prompt_id: string;
    system_prompt: string;
    score: number;
    generation: number;
    color: string;
  };
}

interface TreeEdge {
  id: string;
  source: string;
  target: string;
}

interface RunInfo {
  id: string;
  status: string;
  created_at: string;
  best_score: number | null;
  generations: number;
  total_prompts: number;
}

function PromptNode({ data }: NodeProps) {
  const score = data.score as number;
  return (
    <div
      style={{
        background: "#1e293b",
        border: `2px solid ${data.color}`,
        borderRadius: 8,
        padding: "8px 12px",
        color: "#e2e8f0",
        fontSize: 12,
        cursor: "pointer",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
      }}
    >
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <div style={{ fontWeight: "bold", fontSize: 14 }}>Gen {data.generation as number}</div>
      <div style={{ fontSize: 16, fontWeight: "bold", color: data.color as string }}>
        {score.toFixed(3)}
      </div>
      <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 2 }}>
        {data.system_prompt as string}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </div>
  );
}

const nodeTypes = { promptNode: PromptNode };

export default function RunDetail() {
  const { runId } = useParams<{ runId: string }>();
  const [run, setRun] = useState<RunInfo | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedPrompt, setSelectedPrompt] = useState<string | null>(null);
  const [promptDetailKey, setPromptDetailKey] = useState(0);

  useEffect(() => {
    if (!runId) return;
    fetch(`/api/runs/${runId}`)
      .then((r) => r.json())
      .then(setRun);
    fetch(`/api/runs/${runId}/tree`)
      .then((r) => r.json())
      .then((data) => {
        setNodes(data.nodes);
        setEdges(data.edges);
      });
  }, [runId]);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: { id: string }) => {
      setSelectedPrompt(node.id);
      setPromptDetailKey((k) => k + 1);
    },
    []
  );

  if (!runId) return null;

  return (
    <div style={{ display: "flex", gap: 16, height: "calc(100vh - 100px)" }}>
      <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        <div style={{ marginBottom: 12 }}>
          <Link to="/" style={{ color: "#38bdf8" }}>
            ← Runs
          </Link>
          <span style={{ margin: "0 8px", color: "#475569" }}>/</span>
          <strong>{runId}</strong>
          {run && (
            <span style={{ marginLeft: 16, color: "#94a3b8", fontSize: 14 }}>
              {run.status} · {run.generations} gen · {run.total_prompts} prompts
              {run.best_score != null && (
                <span style={{ marginLeft: 8, color: scoreColor(run.best_score), fontWeight: "bold" }}>
                  best: {run.best_score.toFixed(4)}
                </span>
              )}
            </span>
          )}
        </div>

        <div style={{ flex: 1, background: "#0f172a", borderRadius: 8, border: "1px solid #1e293b" }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            onNodeClick={onNodeClick}
            fitView
            minZoom={0.3}
            maxZoom={2}
            defaultEdgeOptions={{ animated: true, style: { stroke: "#475569" } }}
            style={{ background: "#0f172a" }}
            proOptions={{ hideAttribution: true }}
          >
            <Background color="#1e293b" gap={20} />
            <Controls className="sdopt-controls" />
            <style>{`.sdopt-controls { background: #1e293b !important; } .sdopt-controls button { background: #334155 !important; color: #e2e8f0 !important; border: none !important; }`}</style>
            <MiniMap
              style={{ background: "#0f172a" }}
              nodeColor={(n) => (n.data as any)?.color ?? "#475569"}
              maskColor="rgba(15,23,42,0.8)"
            />
          </ReactFlow>
        </div>
      </div>

      {selectedPrompt && (
        <div
          style={{
            width: 420,
            background: "#1e293b",
            borderRadius: 8,
            border: "1px solid #334155",
            overflow: "auto",
          }}
        >
          <PromptDetail key={promptDetailKey} runId={runId} promptId={selectedPrompt} />
        </div>
      )}
    </div>
  );
}

function scoreColor(s: number): string {
  if (s >= 0.8) return "#22c55e";
  if (s >= 0.5) return "#eab308";
  return "#ef4444";
}
