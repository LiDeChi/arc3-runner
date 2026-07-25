import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { api } from "../api";
import { ReliabilityChart } from "../components/Charts";
import { demoCalibration, demoMetrics } from "../demoData";
import { getHypothesesAtStep, getPredictionAtStep, latestEpisodeTraps } from "../eventSelectors";
import type { CalibrationData, HighConfidenceError, MetricPoint } from "../types";

interface CalibrationProps {
  runId?: string;
  onDemo: () => void;
}

async function enrichError(error: HighConfidenceError): Promise<HighConfidenceError> {
  const events = await api.getEvents(error.episode_id);
  const prediction = getPredictionAtStep(events, error.step_idx);
  const hypotheses = getHypothesesAtStep(events, error.step_idx);
  const actionHypothesis = hypotheses.find((item) => item.action === prediction?.action) ?? hypotheses[0];
  return {
    ...error,
    math: error.math ?? actionHypothesis?.items[0]?.math,
    traps: error.traps ?? latestEpisodeTraps(events)
  };
}

export function Calibration({ runId, onDemo }: CalibrationProps) {
  const navigate = useNavigate();
  const [data, setData] = useState<CalibrationData>(demoCalibration);
  const [metrics, setMetrics] = useState<MetricPoint[]>(demoMetrics);
  const [errors, setErrors] = useState<HighConfidenceError[]>(demoCalibration.high_conf_errors);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      if (!runId) return;
      setLoading(true);
      try {
        const [calibrationRows, metricRows] = await Promise.all([
          api.getCalibration(runId),
          api.getMetrics(runId, ["ece", "overconf"])
        ]);
        const enriched = await Promise.all(calibrationRows.high_conf_errors.slice(0, 25).map(enrichError));
        if (!cancelled) {
          setData(calibrationRows);
          setMetrics(metricRows.length ? metricRows : demoMetrics);
          setErrors(enriched.length ? enriched : calibrationRows.high_conf_errors);
        }
      } catch {
        if (!cancelled) {
          setData(demoCalibration);
          setMetrics(demoMetrics);
          setErrors(demoCalibration.high_conf_errors);
          onDemo();
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [onDemo, runId]);

  return (
    <div className="view-stack">
      <div className="view-heading">
        <div>
          <h2>可信度校准</h2>
          <p>看 agent 的自信是不是靠谱：置信度越高，实际正确率也应该越高。</p>
        </div>
        {loading ? <span className="inline-status">正在读取校准数据</span> : null}
      </div>

      <section className="calibration-grid">
        <ReliabilityChart bins={data.bins} />
        <article className="chart-panel">
          <header>
            <h2>校准误差变化</h2>
          </header>
          <ResponsiveContainer width="100%" height={310}>
            <ComposedChart data={metrics} margin={{ top: 16, right: 20, bottom: 12, left: -12 }}>
              <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="4 4" />
              <XAxis dataKey="episode_idx" stroke="var(--text-muted)" tickLine={false} />
              <YAxis stroke="var(--text-muted)" tickLine={false} />
              <Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)" }} />
              <Line type="monotone" dataKey="ece" stroke="var(--danger)" strokeWidth={2.5} dot={false} />
              <Line type="monotone" dataKey="overconf" stroke="var(--purple)" strokeWidth={2.5} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </article>
      </section>

      <section className="panel">
        <header className="panel-header">
          <h2>高置信错误</h2>
          <span>置信度 &gt; 0.8 但预测错了</span>
        </header>
        <div className="episode-table-wrap">
          <table className="episode-table">
            <thead>
              <tr>
                <th>对局</th>
                <th>步骤</th>
                <th>置信度</th>
                <th>当时最相信的假设</th>
                <th>陷阱</th>
              </tr>
            </thead>
            <tbody>
              {errors.map((error) => (
                <tr
                  key={`${error.episode_id}-${error.step_idx}`}
                  tabIndex={0}
                  onClick={() =>
                    navigate(`/episode?episode=${encodeURIComponent(error.episode_id)}&step=${error.step_idx}`)
                  }
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      navigate(`/episode?episode=${encodeURIComponent(error.episode_id)}&step=${error.step_idx}`);
                    }
                  }}
                >
                  <td>{error.episode_id}</td>
                  <td>{error.step_idx}</td>
                  <td>{Math.round(error.conf * 100)}%</td>
                  <td>
                    <code>{error.math ?? "--"}</code>
                  </td>
                  <td>
                    <div className="chip-row">
                      {(error.traps?.length ? error.traps : ["unknown"]).map((trap) => (
                        <span className="chip" key={trap}>
                          {trap}
                        </span>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
