import { NavLink } from "react-router-dom";
import { useState } from "react";
import type { RunSummary } from "../types";

interface ShellProps {
  runs: RunSummary[];
  selectedRun?: RunSummary;
  selectedRunId?: string;
  episodeCount: number;
  dataSource: "api" | "demo";
  onRunChange: (runId: string) => void;
  onPauseToggle: () => void;
  onStartTraining: (config: { source: "handwritten" | "adversarial"; episodes: number; seed: number }) => void;
  onStartOfficial: (config: { gameId: string; cardId: string; maxSteps: number }) => void;
  children: React.ReactNode;
}

export function AppShell({
  runs,
  selectedRun,
  selectedRunId,
  episodeCount,
  dataSource,
  onRunChange,
  onPauseToggle,
  onStartTraining,
  onStartOfficial,
  children
}: ShellProps) {
  const status = selectedRun?.status ?? "unknown";
  const canToggle = Boolean(selectedRunId) && dataSource === "api";
  const totalEpisodes = Number(selectedRun?.config?.episodes ?? selectedRun?.latest_episodes?.length ?? episodeCount ?? 0);
  const progress = totalEpisodes > 0 ? Math.min(1, episodeCount / totalEpisodes) : 0;
  const statusLabel: Record<string, string> = {
    running: "运行中",
    paused: "已暂停",
    done: "已完成",
    unknown: "未知"
  };

  return (
    <div className="app-shell">
      <aside className="side-rail">
        <div className="brand-block">
          <div className="brand-mark" aria-hidden="true">
            A3
          </div>
          <div>
            <h1>ARC3-Math</h1>
            <p>真实游戏与训练回放控制台</p>
          </div>
        </div>

        <nav className="tabbar" aria-label="Primary views">
          <NavLink to="/dashboard">总览</NavLink>
          <NavLink to="/episode">回放</NavLink>
          <NavLink to="/generator">合成器</NavLink>
          <NavLink to="/calibration">校准</NavLink>
        </nav>

        <section className="rail-section">
          <h2>当前运行</h2>
          <label>
            <span>Run</span>
            <select value={selectedRunId ?? ""} onChange={(event) => onRunChange(event.target.value)}>
              {runs.map((run) => (
                <option value={run.id} key={run.id}>
                  {run.id}
                </option>
              ))}
            </select>
          </label>
          <div className="rail-status-row">
            <div className={`status-pill status-${status}`}>
              <span aria-hidden="true" />
              {statusLabel[status] ?? status}
            </div>
            <div className={`source-pill source-${dataSource}`}>{dataSource === "api" ? "API" : "Demo"}</div>
          </div>
          <div className="training-progress" aria-label="training progress">
            <div>
              <span>训练进度</span>
              <strong>{episodeCount}/{totalEpisodes || "--"}</strong>
            </div>
            <meter min={0} max={1} value={progress} />
          </div>
          <button className="secondary-button" type="button" disabled={!canToggle} onClick={onPauseToggle}>
            {status === "paused" ? "继续" : "暂停"}
          </button>
        </section>

        <section className="rail-section">
          <h2>开始训练</h2>
          <TrainingRunForm onStart={onStartTraining} disabled={false} />
        </section>

        <section className="rail-section">
          <h2>真实游戏</h2>
          <OfficialRunForm onStart={onStartOfficial} disabled={false} />
        </section>
      </aside>

      <main className="app-main">{children}</main>
    </div>
  );
}

function TrainingRunForm({
  disabled,
  onStart
}: {
  disabled: boolean;
  onStart: (config: { source: "handwritten" | "adversarial"; episodes: number; seed: number }) => void;
}) {
  const [source, setSource] = useState<"handwritten" | "adversarial">("adversarial");
  const [episodes, setEpisodes] = useState(30);
  const [seed, setSeed] = useState(7);

  return (
    <form
      className="training-run-form"
      onSubmit={(event) => {
        event.preventDefault();
        onStart({ source, episodes, seed });
      }}
    >
      <label>
        <span>训练源</span>
        <select value={source} onChange={(event) => setSource(event.target.value as "handwritten" | "adversarial")} disabled={disabled}>
          <option value="adversarial">对抗合成训练</option>
          <option value="handwritten">5 个手写游戏循环</option>
        </select>
      </label>
      <label>
        <span>局数</span>
        <input
          type="number"
          min={1}
          max={1000}
          value={episodes}
          onChange={(event) => setEpisodes(Number(event.target.value))}
          disabled={disabled}
        />
      </label>
      <label>
        <span>Seed</span>
        <input
          type="number"
          value={seed}
          onChange={(event) => setSeed(Number(event.target.value))}
          disabled={disabled}
        />
      </label>
      <button type="submit" disabled={disabled}>
        开始训练
      </button>
    </form>
  );
}

function OfficialRunForm({
  disabled,
  onStart
}: {
  disabled: boolean;
  onStart: (config: { gameId: string; cardId: string; maxSteps: number }) => void;
}) {
  const [gameId, setGameId] = useState("");
  const [cardId, setCardId] = useState("");
  const [maxSteps, setMaxSteps] = useState(10);

  return (
    <form
      className="official-run-form"
      onSubmit={(event) => {
        event.preventDefault();
        onStart({ gameId: gameId.trim(), cardId: cardId.trim(), maxSteps });
      }}
    >
      <input
        aria-label="Official game id"
        placeholder="官方 game_id"
        value={gameId}
        onChange={(event) => setGameId(event.target.value)}
        disabled={disabled}
      />
      <input
        aria-label="Official card id"
        placeholder="card_id 可选"
        value={cardId}
        onChange={(event) => setCardId(event.target.value)}
        disabled={disabled}
      />
      <input
        aria-label="Official max steps"
        type="number"
        min={1}
        max={200}
        value={maxSteps}
        onChange={(event) => setMaxSteps(Number(event.target.value))}
        disabled={disabled}
      />
      <button type="submit" disabled={disabled}>
        启动官方
      </button>
    </form>
  );
}
