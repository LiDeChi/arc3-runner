import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { GridCanvas } from "../components/GridCanvas";
import {
  demoEpisodes,
  demoEvents,
  demoGameSpec,
  demoPreviewForEpisode,
  demoTraps
} from "../demoData";
import { getGameSpec, latestEpisodeGrid, latestEpisodeTraps } from "../eventSelectors";
import type { ArcEvent, EpisodePreview, GameSpec, GeneratorUpdatePayload, TrapDatum } from "../types";

interface GeneratorProps {
  runId?: string;
  onDemo: () => void;
}

function heatColor(value: number): string {
  const clamped = Math.max(0, Math.min(1, value));
  const hue = 135 - clamped * 135;
  return `hsl(${hue} 72% 42% / 0.26)`;
}

function TrapHeatmap({ traps }: { traps: TrapDatum[] }) {
  return (
    <section className="panel">
      <header className="panel-header">
        <h2>陷阱效果热力图</h2>
        <span>越红表示越能骗到 agent</span>
      </header>
      <div className="heatmap-table-wrap">
        <table className="heatmap-table">
          <thead>
            <tr>
              <th>陷阱组合</th>
              <th>次数</th>
              <th>胜率</th>
              <th>高置信错误</th>
              <th>UCB</th>
            </tr>
          </thead>
          <tbody>
            {traps.map((trap) => (
              <tr key={trap.arm}>
                <td>
                  <code>{trap.arm}</code>
                </td>
                <td>{trap.plays}</td>
                <td style={{ background: heatColor(1 - trap.agent_win_rate) }}>{Math.round(trap.agent_win_rate * 100)}%</td>
                <td style={{ background: heatColor(trap.overconf_mean) }}>{trap.overconf_mean.toFixed(2)}</td>
                <td style={{ background: heatColor(Math.min(1, trap.ucb / 1.5)) }}>{trap.ucb.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ArmTimeline({ updates }: { updates: ArcEvent[] }) {
  const latest = updates.slice(-50);
  return (
    <section className="panel">
      <header className="panel-header">
        <h2>课程选择时间线</h2>
        <span>{latest.length} 次更新</span>
      </header>
      <div className="arm-timeline">
        {latest.map((event, index) => (
          <div className="arm-bar" key={event.id ?? `${event.step_idx}-${index}`}>
            <span
              style={{
                height: `${Math.max(
                  12,
                  Math.min(96, ((event.payload as unknown as GeneratorUpdatePayload).reward ?? 0) * 92)
                )}px`
              }}
              title={`${(event.payload as unknown as GeneratorUpdatePayload).arm}: ${(
                (event.payload as unknown as GeneratorUpdatePayload).reward ?? 0
              ).toFixed(2)}`}
            />
            <small>{event.step_idx}</small>
          </div>
        ))}
        {!latest.length ? <div className="empty-panel">还没有 generator_update 事件。只有对抗合成 run 才会产生这里的数据。</div> : null}
      </div>
    </section>
  );
}

function GameGallery({ previews }: { previews: EpisodePreview[] }) {
  const navigate = useNavigate();
  return (
    <section className="panel">
      <header className="panel-header">
        <h2>合成游戏画廊</h2>
        <span>最近 {previews.length} 局</span>
      </header>
      <div className="game-gallery">
        {previews.map((preview) => (
          <button
            className="game-card"
            type="button"
            key={preview.episode.id}
            onClick={() => navigate(`/episode?episode=${encodeURIComponent(preview.episode.id)}`)}
          >
            <GridCanvas grid={preview.grid} mini label={preview.episode.game_id} />
            <strong>#{preview.episode.idx} {preview.episode.game_id}</strong>
            <span>{preview.episode.result} in {preview.episode.steps} steps</span>
            <div className="chip-row">
              {(preview.traps.length ? preview.traps : ["none"]).map((trap) => (
                <span className="chip" key={trap}>
                  {trap}
                </span>
              ))}
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}

async function previewFromEpisode(episodeId: string) {
  const events = await api.getEvents(episodeId);
  return {
    events,
    spec: getGameSpec(events),
    grid: latestEpisodeGrid(events),
    traps: latestEpisodeTraps(events)
  };
}

export function Generator({ runId, onDemo }: GeneratorProps) {
  const [traps, setTraps] = useState<TrapDatum[]>(demoTraps);
  const [updates, setUpdates] = useState<ArcEvent[]>(demoEvents.filter((event) => event.type === "generator_update"));
  const [previews, setPreviews] = useState<EpisodePreview[]>(demoEpisodes.map(demoPreviewForEpisode));
  const [previewGame, setPreviewGame] = useState<GameSpec>(demoGameSpec);
  const [previewSeed, setPreviewSeed] = useState(43);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      if (!runId) return;
      setLoading(true);
      try {
        const [trapRows, episodeRows] = await Promise.all([api.getTraps(runId), api.getEpisodes(runId, 12, 0)]);
        const loadedPreviews: EpisodePreview[] = [];
        const loadedUpdates: ArcEvent[] = [];

        for (const episode of episodeRows.slice(0, 12)) {
          try {
            const episodePreview = await previewFromEpisode(episode.id);
            loadedPreviews.push({
              episode,
              spec: episodePreview.spec,
              grid: episodePreview.grid,
              traps: episodePreview.traps
            });
            loadedUpdates.push(
              ...episodePreview.events.filter((event) => event.type === "generator_update")
            );
          } catch {
            loadedPreviews.push(demoPreviewForEpisode(episode));
          }
        }

        if (!cancelled) {
          setTraps(trapRows.length ? trapRows : demoTraps);
          setPreviews(loadedPreviews.length ? loadedPreviews : demoEpisodes.map(demoPreviewForEpisode));
          setUpdates(loadedUpdates.length ? loadedUpdates : updates);
        }
      } catch {
        if (!cancelled) {
          setTraps(demoTraps);
          setUpdates(demoEvents.filter((event) => event.type === "generator_update"));
          setPreviews(demoEpisodes.map(demoPreviewForEpisode));
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

  const sortedTraps = useMemo(() => [...traps].sort((a, b) => b.overconf_mean - a.overconf_mean), [traps]);

  async function handlePreview() {
    try {
      const next = await api.previewGame(previewSeed);
      setPreviewGame(next);
    } catch {
      setPreviewGame(demoGameSpec);
      onDemo();
    } finally {
      setPreviewSeed((seed) => seed + 1);
    }
  }

  return (
    <div className="view-stack">
      <div className="view-heading">
        <div>
          <h2>对抗合成器</h2>
          <p>这里看的是“哪些陷阱还在骗到 agent”。真实官方游戏优先；合成器用于后续课程训练。</p>
        </div>
        <div className="preview-controls">
          {loading ? <span className="inline-status">正在读取合成器数据</span> : null}
          <button type="button" onClick={handlePreview}>
            预览一个合成游戏
          </button>
        </div>
      </div>

      <TrapHeatmap traps={sortedTraps} />
      <ArmTimeline updates={updates} />

      <section className="preview-strip">
        <div>
          <h3>最新预览</h3>
          <p>{previewGame.id}</p>
        </div>
        <GridCanvas grid={previewGame.tiles} mini label="Preview tiles" />
        <div className="chip-row">
          {(previewGame.meta?.traps ?? ["adversarial"]).map((trap) => (
            <span className="chip" key={trap}>
              {trap}
            </span>
          ))}
        </div>
      </section>

      <GameGallery previews={previews} />
    </div>
  );
}
