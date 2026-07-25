import { Suspense, lazy, useCallback, useEffect, useMemo, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { api } from "./api";
import { AppShell } from "./components/Shell";
import { demoRuns } from "./demoData";
import type { RunSummary } from "./types";

const Dashboard = lazy(() => import("./views/Dashboard").then((module) => ({ default: module.Dashboard })));
const EpisodeViewer = lazy(() => import("./views/EpisodeViewer").then((module) => ({ default: module.EpisodeViewer })));
const Generator = lazy(() => import("./views/Generator").then((module) => ({ default: module.Generator })));
const Calibration = lazy(() => import("./views/Calibration").then((module) => ({ default: module.Calibration })));

export default function App() {
  const [runs, setRuns] = useState<RunSummary[]>(demoRuns);
  const [selectedRunId, setSelectedRunId] = useState<string>(demoRuns[0]?.id ?? "");
  const [episodeCounts, setEpisodeCounts] = useState<Record<string, number>>({});
  const [dataSource, setDataSource] = useState<"api" | "demo">("api");

  const markDemo = useCallback(() => {
    setDataSource("demo");
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadRuns() {
      try {
        const rows = await api.getRuns();
        if (cancelled) return;
        if (rows.length) {
          setRuns(rows);
          setSelectedRunId((current) => (rows.some((run) => run.id === current) ? current : rows[0].id));
          setDataSource("api");
        } else {
          setRuns(demoRuns);
          setSelectedRunId(demoRuns[0].id);
          setDataSource("demo");
        }
      } catch {
        if (cancelled) return;
        setRuns(demoRuns);
        setSelectedRunId(demoRuns[0].id);
        setDataSource("demo");
      }
    }

    void loadRuns();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function refreshRuns() {
      try {
        const rows = await api.getRuns();
        if (cancelled) return;
        if (rows.length) {
          setRuns(rows);
          setDataSource("api");
        }
        const activeRunId = rows.some((run) => run.id === selectedRunId) ? selectedRunId : rows[0]?.id;
        if (activeRunId && activeRunId !== selectedRunId) {
          setSelectedRunId(activeRunId);
        }
        if (activeRunId) {
          const episodes = await api.getEpisodes(activeRunId, 1000, 0);
          if (!cancelled) {
            setEpisodeCounts((current) => ({ ...current, [activeRunId]: episodes.length }));
          }
        }
      } catch {
        if (!cancelled) markDemo();
      }
    }

    void refreshRuns();
    const interval = window.setInterval(refreshRuns, 1800);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [markDemo, selectedRunId]);

  const selectedRun = useMemo(
    () => runs.find((run) => run.id === selectedRunId) ?? runs[0],
    [runs, selectedRunId]
  );

  async function handlePauseToggle() {
    if (!selectedRun) return;
    try {
      if (selectedRun.status === "paused") {
        await api.resumeRun(selectedRun.id);
        setRuns((current) => current.map((run) => (run.id === selectedRun.id ? { ...run, status: "running" } : run)));
      } else {
        await api.pauseRun(selectedRun.id);
        setRuns((current) => current.map((run) => (run.id === selectedRun.id ? { ...run, status: "paused" } : run)));
      }
    } catch {
      markDemo();
    }
  }

  async function handleStartTraining(config: { source: "handwritten" | "adversarial"; episodes: number; seed: number }) {
    try {
      const created = await api.createRun({
        episodes: config.episodes,
        game_source: config.source,
        seed: config.seed,
        async: true
      });
      setSelectedRunId(created.run_id);
      setEpisodeCounts((current) => ({ ...current, [created.run_id]: 0 }));
      const rows = await api.getRuns();
      if (rows.length) setRuns(rows);
      setDataSource("api");
    } catch {
      markDemo();
    }
  }

  async function handleStartOfficial(config: { gameId: string; cardId: string; maxSteps: number }) {
    try {
      const created = await api.createRun({
        episodes: 1,
        game_source: "official",
        game_id: config.gameId || undefined,
        card_id: config.cardId || undefined,
        max_steps: config.maxSteps,
        async: true
      });
      const rows = await api.getRuns();
      setRuns(rows.length ? rows : runs);
      setSelectedRunId(created.run_id);
      setDataSource("api");
    } catch {
      markDemo();
    }
  }

  return (
    <AppShell
      runs={runs}
      selectedRun={selectedRun}
      selectedRunId={selectedRun?.id}
      episodeCount={episodeCounts[selectedRun?.id ?? ""] ?? selectedRun?.latest_episodes?.length ?? 0}
      dataSource={dataSource}
      onRunChange={setSelectedRunId}
      onPauseToggle={handlePauseToggle}
      onStartTraining={handleStartTraining}
      onStartOfficial={handleStartOfficial}
    >
      <Suspense fallback={<div className="route-loading">Loading view</div>}>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard runId={selectedRun?.id} onDemo={markDemo} />} />
          <Route
            path="/episode"
            element={<EpisodeViewer runId={selectedRun?.id} selectedRun={selectedRun} dataSource={dataSource} onDemo={markDemo} />}
          />
          <Route path="/generator" element={<Generator runId={selectedRun?.id} onDemo={markDemo} />} />
          <Route path="/calibration" element={<Calibration runId={selectedRun?.id} onDemo={markDemo} />} />
        </Routes>
      </Suspense>
    </AppShell>
  );
}
