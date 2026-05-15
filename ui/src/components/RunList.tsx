import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

interface Run {
  id: string;
  created_at: string;
  status: string;
  best_score: number | null;
  model: string;
  scenario: string;
}

export default function RunList() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/runs")
      .then((r) => r.json())
      .then(setRuns)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>Loading...</p>;

  if (runs.length === 0) {
    return (
      <div style={{ textAlign: "center", marginTop: 80 }}>
        <h2>No runs yet</h2>
        <p style={{ color: "#94a3b8" }}>
          Run <code>sdopt run examples/config.yaml</code> in the terminal
        </p>
      </div>
    );
  }

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>Runs</h2>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {runs.map((r) => (
          <Link
            key={r.id}
            to={`/run/${r.id}`}
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "12px 16px",
              background: "#1e293b",
              borderRadius: 8,
              textDecoration: "none",
              color: "#e2e8f0",
              border: "1px solid #334155",
            }}
          >
            <div>
              <strong>{r.id}</strong>
              <span style={{ marginLeft: 12, color: "#94a3b8", fontSize: 14 }}>
                {r.created_at?.slice(0, 19) ?? "?"}
              </span>
              <span
                style={{
                  marginLeft: 12,
                  fontSize: 12,
                  color: r.status === "completed" ? "#22c55e" : "#ef4444",
                }}
              >
                {r.status}
              </span>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 18, fontWeight: "bold", color: scoreColor(r.best_score ?? 0) }}>
                {r.best_score != null ? r.best_score.toFixed(4) : "-"}
              </div>
              <div style={{ fontSize: 12, color: "#94a3b8" }}>{r.model ?? "?"}</div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

function scoreColor(s: number): string {
  if (s >= 0.8) return "#22c55e";
  if (s >= 0.5) return "#eab308";
  return "#ef4444";
}
