import { useEffect, useState, useRef } from "react";

interface ToolCall {
  tool_name: string;
  input: string;
  output: string;
}

interface TestResultDetail {
  input: string;
  expected_tool_calls: string[] | null;
  response: string;
  tool_calls: ToolCall[];
  scores: Record<string, number>;
}

interface PromptData {
  prompt_id: string;
  system_prompt: string;
  aggregate_score: number;
  generation: number;
  strategy: string | null;
  parent_id: string | null;
  test_results: TestResultDetail[];
}

function copy(text: string) {
  navigator.clipboard.writeText(text);
}

export default function PromptDetail({
  runId,
  promptId,
}: {
  runId: string;
  promptId: string;
}) {
  const [data, setData] = useState<PromptData | null>(null);
  const [activeTab, setActiveTab] = useState(0);

  useEffect(() => {
    fetch(`/api/runs/${runId}/prompts/${promptId}`)
      .then((r) => r.json())
      .then(setData);
  }, [runId, promptId]);

  if (!data) return <p style={{ padding: 16 }}>Loading...</p>;

  const tc = data.test_results[activeTab];

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12, height: "100%" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ margin: 0, fontSize: 16 }}>
          Prompt {data.prompt_id.slice(0, 8)}
          <span style={{ marginLeft: 8, fontSize: 12, color: "#94a3b8" }}>
            Gen {data.generation} · {data.strategy ?? "?"}
          </span>
        </h3>
        <button
          onClick={() => copy(data.system_prompt)}
          style={{
            background: "#334155",
            border: "none",
            color: "#e2e8f0",
            padding: "4px 10px",
            borderRadius: 4,
            cursor: "pointer",
            fontSize: 12,
          }}
        >
          Copy
        </button>
      </div>

      <div
        style={{
          background: "#0f172a",
          borderRadius: 6,
          padding: 10,
          fontSize: 12,
          fontFamily: "monospace",
          whiteSpace: "pre-wrap",
          maxHeight: 140,
          overflow: "auto",
          border: "1px solid #334155",
        }}
      >
        {data.system_prompt}
      </div>

      <div style={{ fontSize: 18, fontWeight: "bold", color: scoreColor(data.aggregate_score) }}>
        Score: {data.aggregate_score.toFixed(4)}
      </div>

      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
        {data.test_results.map((_, i) => (
          <button
            key={i}
            onClick={() => setActiveTab(i)}
            style={{
              background: i === activeTab ? "#334155" : "transparent",
              border: "1px solid #475569",
              color: "#e2e8f0",
              padding: "4px 10px",
              borderRadius: 4,
              cursor: "pointer",
              fontSize: 11,
            }}
          >
            Test {i}
          </button>
        ))}
      </div>

      {tc && (
        <div
          style={{
            flex: 1,
            overflow: "auto",
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          <MessageBubble label="User" text={tc.input} color="#3b82f6" />

          {tc.tool_calls.map((t, i) => (
            <div key={i}>
              <MessageBubble
                label={`Tool: ${t.tool_name}`}
                text={`Input: ${t.input}\nOutput: ${t.output}`}
                color="#a855f7"
              />
            </div>
          ))}

          <MessageBubble label="Assistant" text={tc.response} color="#22c55e" />

          <div
            style={{
              display: "flex",
              gap: 8,
              flexWrap: "wrap",
              fontSize: 12,
            }}
          >
            {Object.entries(tc.scores).map(([k, v]) => {
              if (k === "aggregate") return null;
              return (
                <span
                  key={k}
                  style={{
                    background: "#0f172a",
                    padding: "4px 8px",
                    borderRadius: 4,
                    border: `1px solid ${scoreColor(v as number)}`,
                    color: scoreColor(v as number),
                  }}
                >
                  {k}: {v.toFixed(3)}
                </span>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function MessageBubble({
  label,
  text,
  color,
}: {
  label: string;
  text: string;
  color: string;
}) {
  return (
    <div>
      <div style={{ fontSize: 11, fontWeight: "bold", color, marginBottom: 2 }}>
        {label}
      </div>
      <div
        style={{
          background: "#0f172a",
          borderRadius: 6,
          padding: 8,
          fontSize: 13,
          whiteSpace: "pre-wrap",
          border: `1px solid ${color}33`,
          fontFamily: "monospace",
        }}
      >
        {text}
      </div>
    </div>
  );
}

function scoreColor(s: number): string {
  if (s >= 0.8) return "#22c55e";
  if (s >= 0.5) return "#eab308";
  return "#ef4444";
}
