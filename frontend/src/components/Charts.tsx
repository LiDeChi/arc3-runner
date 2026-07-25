import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import type { CalibrationBin, MetricPoint } from "../types";

function percent(value?: number): string {
  return typeof value === "number" ? `${Math.round(value * 100)}%` : "--";
}

function number(value?: number, digits = 2): string {
  return typeof value === "number" ? value.toFixed(digits) : "--";
}

export function MetricCards({ metrics }: { metrics: MetricPoint[] }) {
  const latest = metrics.at(-1);
  const cards = [
    { label: "解题率", value: percent(latest?.solve_rate), hint: "最近 20 局" },
    { label: "中位步数", value: number(latest?.median_steps, 0), hint: "越少越好" },
    { label: "校准误差", value: number(latest?.ece, 3), hint: "ECE，越低越准" },
    { label: "高置信错误", value: percent(latest?.high_conf_error_rate ?? latest?.overconf), hint: "很自信但错了" },
    { label: "当前难度", value: number(latest?.difficulty, 2), hint: "课程难度" }
  ];

  return (
    <section className="metric-grid" aria-label="Run metrics">
      {cards.map((card) => (
        <article className="metric-card" key={card.label}>
          <span>{card.label}</span>
          <strong>{card.value}</strong>
          <small>{card.hint}</small>
        </article>
      ))}
    </section>
  );
}

export function TrendCharts({ metrics }: { metrics: MetricPoint[] }) {
  return (
    <section className="chart-grid">
      <article className="chart-panel chart-panel-wide">
        <header>
        <h2>解题率与难度</h2>
        </header>
        <ResponsiveContainer width="100%" height={260}>
          <ComposedChart data={metrics} margin={{ top: 12, right: 20, bottom: 8, left: 0 }}>
            <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="4 4" />
            <XAxis dataKey="episode_idx" stroke="var(--text-muted)" tickLine={false} />
            <YAxis yAxisId="left" stroke="var(--accent)" tickLine={false} domain={[0, 1]} />
            <YAxis yAxisId="right" orientation="right" stroke="var(--warning)" tickLine={false} />
            <Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)" }} />
            <Legend />
            <Line yAxisId="left" type="monotone" dataKey="solve_rate" stroke="var(--accent)" strokeWidth={2.5} dot={false} />
            <Line yAxisId="right" type="monotone" dataKey="difficulty" stroke="var(--warning)" strokeWidth={2.5} dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </article>

      <article className="chart-panel">
        <header>
          <h2>校准误差 ECE</h2>
        </header>
        <ResponsiveContainer width="100%" height={230}>
          <ComposedChart data={metrics} margin={{ top: 12, right: 14, bottom: 8, left: -16 }}>
            <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="4 4" />
            <XAxis dataKey="episode_idx" stroke="var(--text-muted)" tickLine={false} />
            <YAxis stroke="var(--text-muted)" tickLine={false} />
            <Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)" }} />
            <Line type="monotone" dataKey="ece" stroke="var(--danger)" strokeWidth={2.5} dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </article>

      <article className="chart-panel">
        <header>
          <h2>高置信错误</h2>
        </header>
        <ResponsiveContainer width="100%" height={230}>
          <ComposedChart data={metrics} margin={{ top: 12, right: 14, bottom: 8, left: -16 }}>
            <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="4 4" />
            <XAxis dataKey="episode_idx" stroke="var(--text-muted)" tickLine={false} />
            <YAxis stroke="var(--text-muted)" tickLine={false} />
            <Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)" }} />
            <Line type="monotone" dataKey="overconf" stroke="var(--purple)" strokeWidth={2.5} dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </article>
    </section>
  );
}

export function ReliabilityChart({ bins }: { bins: CalibrationBin[] }) {
  const data = bins.map((bin, index) => ({
    ...bin,
    bin: `${index + 1}`,
    ideal: bin.mean_conf
  }));

  return (
    <article className="chart-panel chart-panel-wide">
      <header>
        <h2>可靠性图</h2>
      </header>
      <ResponsiveContainer width="100%" height={310}>
        <BarChart data={data} margin={{ top: 16, right: 22, bottom: 12, left: -10 }}>
          <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="4 4" />
          <XAxis dataKey="bin" stroke="var(--text-muted)" tickLine={false} />
          <YAxis stroke="var(--text-muted)" tickLine={false} domain={[0, 1]} />
          <Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)" }} />
          <Legend />
          <ReferenceLine segment={[{ x: "1", y: 0.1 }, { x: "10", y: 1 }]} stroke="var(--text-muted)" strokeDasharray="5 5" />
          <Bar dataKey="accuracy" name="实际正确率" radius={[4, 4, 0, 0]}>
            {data.map((bin) => (
              <Cell key={bin.bin} fill={Math.abs(bin.accuracy - bin.mean_conf) > 0.12 ? "var(--danger)" : "var(--accent)"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </article>
  );
}
