import { useEffect, useState } from "react";

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

function ChatView({ tc }: { tc: TestResultDetail }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ fontSize: 11, fontWeight: "bold", color: "#3b82f6" }}>User</div>
      <div style={{
        background: "#0f172a", borderRadius: 6, padding: 8, fontSize: 13,
        whiteSpace: "pre-wrap", border: "1px solid #3b82f633", fontFamily: "monospace",
      }}>
        {tc.input}
      </div>

      {tc.tool_calls.map((t, i) => (
        <div key={i}>
          <div style={{ fontSize: 11, fontWeight: "bold", color: "#a855f7" }}>
            Tool: {t.tool_name}
          </div>
          <div style={{
            background: "#0f172a", borderRadius: 6, padding: 8, fontSize: 13,
            whiteSpace: "pre-wrap", border: "1px solid #a855f733", fontFamily: "monospace",
          }}>
            {t.input}{"\n→ "}{t.output}
          </div>
        </div>
      ))}

      <div style={{ fontSize: 11, fontWeight: "bold", color: "#22c55e" }}>Assistant</div>
      <div style={{
        background: "#0f172a", borderRadius: 6, padding: 8, fontSize: 13,
        whiteSpace: "pre-wrap", border: "1px solid #22c55e33", fontFamily: "monospace",
      }}>
        {tc.response}
      </div>

      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 4 }}>
        {Object.entries(tc.scores).map(([k, v]) => {
          if (k === "aggregate") return null;
          return (
            <span key={k} style={{
              background: "#0f172a", padding: "3px 6px", borderRadius: 4,
              border: `1px solid ${scoreColor(v)}`, color: scoreColor(v), fontSize: 11,
            }}>
              {k}: {v.toFixed(3)}
            </span>
          );
        })}
      </div>
    </div>
  );
}

export default function PromptDetail({
  runId,
  promptId,
}: {
  runId: string;
  promptId: string;
}) {
  const [data, setData] = useState<PromptData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTest, setActiveTest] = useState(0);

  useEffect(() => {
    fetch(`/api/runs/${runId}/prompts/${promptId}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setData)
      .catch((e) => setError(e.message));
  }, [runId, promptId]);

  if (error) return <p style={{ padding: 16, color: "#ef4444" }}>Error: {error}</p>;
  if (!data) return <p style={{ padding: 16, color: "#94a3b8" }}>Loading...</p>;

  const activeTc = data.test_results[activeTest];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ padding: "12px 16px", borderBottom: "1px solid #334155" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <span style={{ fontSize: 14, fontWeight: "bold" }}>
              Prompt {data.prompt_id.slice(0, 8)}
            </span>
            <span style={{ marginLeft: 8, fontSize: 12, color: "#94a3b8" }}>
              Gen {data.generation} · {data.strategy ?? "?"}
            </span>
          </div>
          <button onClick={() => copy(data.system_prompt)} style={{
            background: "#334155", border: "none", color: "#e2e8f0",
            padding: "4px 10px", borderRadius: 4, cursor: "pointer", fontSize: 12,
          }}>
            Copy prompt
          </button>
        </div>
        <div style={{ marginTop: 8, fontSize: 12, color: scoreColor(data.aggregate_score), fontWeight: "bold" }}>
          Score: {data.aggregate_score.toFixed(4)}
        </div>
        <div style={{
          marginTop: 8, background: "#0f172a", borderRadius: 6, padding: 8,
          fontSize: 11, fontFamily: "monospace", whiteSpace: "pre-wrap",
          maxHeight: 80, overflow: "auto", border: "1px solid #334155",
        }}>
          {data.system_prompt}
        </div>
      </div>

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <div style={{
          width: 180, borderRight: "1px solid #334155",
          overflow: "auto", flexShrink: 0,
        }}>
          {data.test_results.map((tc, i) => (
            <div key={i} onClick={() => setActiveTest(i)} style={{
              padding: "8px 10px", cursor: "pointer",
              background: i === activeTest ? "#1e293b" : "transparent",
              borderBottom: "1px solid #1e293b", fontSize: 11,
            }}>
              <div style={{ color: "#e2e8f0", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {tc.input.slice(0, 40)}
              </div>
              <div style={{ marginTop: 2, fontSize: 10, color: scoreColor(tc.scores?.aggregate ?? 0) }}>
                {(tc.scores?.aggregate ?? 0).toFixed(3)}
              </div>
            </div>
          ))}
        </div>

        <div style={{ flex: 1, overflow: "auto", padding: 12 }}>
          {activeTc ? <ChatView tc={activeTc} /> : (
            <p style={{ color: "#94a3b8", fontSize: 12 }}>No test results</p>
          )}
        </div>
      </div>
    </div>
  );
}

function scoreColor(s: number): string {
  if (s >= 0.8) return "#22c55e";
  if (s >= 0.5) return "#eab308";
  return "#ef4444";
}