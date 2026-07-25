import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { MetricCards, TrendCharts } from "../components/Charts";
import { GridCanvas } from "../components/GridCanvas";
import { demoEpisodes, demoMetrics, demoPreviewForEpisode } from "../demoData";
import { getGameSpec, latestEpisodeGrid, latestEpisodeTraps } from "../eventSelectors";
import type { EpisodePreview, EpisodeSummary, MetricPoint } from "../types";

interface DashboardProps {
  runId?: string;
  onDemo: () => void;
}

async function loadPreview(episode: EpisodeSummary): Promise<EpisodePreview> {
  const events = await api.getEvents(episode.id);
  return {
    episode,
    spec: getGameSpec(events),
    grid: latestEpisodeGrid(events),
    traps: latestEpisodeTraps(events)
  };
}

export function Dashboard({ runId, onDemo }: DashboardProps) {
  const navigate = useNavigate();
  const [metrics, setMetrics] = useState<MetricPoint[]>(demoMetrics);
  const [episodes, setEpisodes] = useState<EpisodeSummary[]>(demoEpisodes);
  const [previews, setPreviews] = useState<EpisodePreview[]>(demoEpisodes.map(demoPreviewForEpisode));
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      if (!runId) return;
      setLoading(true);

      try {
        const [metricRows, episodeRows] = await Promise.all([
          api.getMetrics(runId, ["solve_rate", "difficulty", "ece", "overconf", "high_conf_error_rate", "median_steps"]),
          api.getEpisodes(runId, 12, 0)
        ]);
        if (cancelled) return;
        setMetrics(metricRows.length ? metricRows : demoMetrics);
        setEpisodes(episodeRows.length ? episodeRows : demoEpisodes);

        const previewRows = await Promise.all(
          (episodeRows.length ? episodeRows : demoEpisodes).slice(0, 8).map(async (episode) => {
            try {
              return await loadPreview(episode);
            } catch {
              return demoPreviewForEpisode(episode);
            }
          })
        );
        if (!cancelled) setPreviews(previewRows);
      } catch {
        if (cancelled) return;
        setMetrics(demoMetrics);
        setEpisodes(demoEpisodes);
        setPreviews(demoEpisodes.map(demoPreviewForEpisode));
        onDemo();
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    const interval = window.setInterval(load, 2500);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [onDemo, runId]);

  return (
    <div className="view-stack">
      <div className="view-heading">
        <div>
          <h2>训练总览</h2>
          <p>先看这一轮有没有变好：解题率、步数、校准误差、高置信错误和最近对局。</p>
        </div>
        {loading ? <span className="inline-status">正在读取 API 数据</span> : null}
      </div>

      <MetricCards metrics={metrics} />
      <TrendCharts metrics={metrics} />

      <section className="panel">
        <header className="panel-header">
          <h2>最近对局</h2>
          <span>显示 {episodes.length} 局</span>
        </header>
        <div className="episode-table-wrap">
          <table className="episode-table">
            <thead>
              <tr>
                <th>#</th>
                <th>游戏</th>
                <th>棋盘</th>
                <th>陷阱</th>
                <th>结果</th>
                <th>步数</th>
                <th>平均置信度</th>
              </tr>
            </thead>
            <tbody>
              {previews.map((preview) => (
                <tr
                  key={preview.episode.id}
                  tabIndex={0}
                  onClick={() => navigate(`/episode?episode=${encodeURIComponent(preview.episode.id)}`)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") navigate(`/episode?episode=${encodeURIComponent(preview.episode.id)}`);
                  }}
                >
                  <td>{preview.episode.idx}</td>
                  <td>
                    <strong>{preview.episode.game_id}</strong>
                  </td>
                  <td>
                    <GridCanvas grid={preview.grid} mini label={`Episode ${preview.episode.idx}`} />
                  </td>
                  <td>
                    <div className="chip-row">
                      {(preview.traps.length ? preview.traps : ["none"]).map((trap) => (
                        <span className="chip" key={trap}>
                          {trap}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td>
                    <span className={`result result-${preview.episode.result}`}>{preview.episode.result}</span>
                  </td>
                  <td>{preview.episode.steps}</td>
                  <td>{Math.round(preview.episode.avg_conf * 100)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
