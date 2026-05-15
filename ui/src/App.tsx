import { Routes, Route, Link } from "react-router-dom";
import RunList from "./components/RunList";
import RunDetail from "./components/RunDetail";

export default function App() {
  return (
    <div style={{ minHeight: "100vh", background: "#0f172a", color: "#e2e8f0" }}>
      <header
        style={{
          borderBottom: "1px solid #1e293b",
          padding: "12px 24px",
          display: "flex",
          alignItems: "center",
          gap: 16,
        }}
      >
        <h1 style={{ margin: 0, fontSize: 20 }}>
          <Link to="/" style={{ color: "#38bdf8", textDecoration: "none" }}>
            SD Optimizer
          </Link>
        </h1>
      </header>
      <main style={{ padding: 24 }}>
        <Routes>
          <Route path="/" element={<RunList />} />
          <Route path="/run/:runId" element={<RunDetail />} />
        </Routes>
      </main>
    </div>
  );
}
