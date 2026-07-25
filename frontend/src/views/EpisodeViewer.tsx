import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { GridCanvas } from "../components/GridCanvas";
import { demoEpisodes } from "../demoData";
import {
  buildTimeline,
  getActionAtStep,
  getEpisodeEnd,
  getEventsAtStep,
  getGameSpec,
  getLastDecisionStep,
  getHypothesesAtStep,
  getObservationAtStep,
  getObservationPayloadAtStep,
  getOutcomeAtStep,
  getPlanAtStep,
  getPredictionAtStep,
  getPreviousHypotheses,
  getRevisionsAtStep
} from "../eventSelectors";
import { useRunStream } from "../hooks/useRunStream";
import type {
  ActionHypotheses,
  ArcEvent,
  BeliefRevisionPayload,
  EpisodeSummary,
  GameAction,
  GameSpec,
  Grid,
  HypothesisItem,
  ObservationPayload,
  PlanPayload,
  RunSummary
} from "../types";

interface EpisodeViewerProps {
  runId?: string;
  selectedRun?: RunSummary;
  dataSource: "api" | "demo";
  onDemo: () => void;
}

function pct(value: number | undefined): string {
  return typeof value === "number" ? `${Math.round(value * 100)}%` : "--";
}

function streamLabel(state: string): string {
  const labels: Record<string, string> = {
    idle: "空闲",
    loading: "加载中",
    connected: "已连接",
    disconnected: "已断开",
    demo: "演示数据",
    error: "连接错误"
  };
  return labels[state] ?? state;
}

function formatJson(value: unknown): string {
  if (value === undefined) return "{}";
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function sourceLabel(gameSource?: string): string {
  switch (gameSource) {
    case "official":
      return "官方线上 ARC API";
    case "adversarial":
      return "本地 generator 难例";
    case "handwritten":
      return "本地 SDK 手写游戏";
    default:
      return gameSource ? String(gameSource) : "未知";
  }
}

function sourceVerdict(dataSource: "api" | "demo", streamIsDemo: boolean, gameSource?: string): string {
  if (dataSource === "demo" || streamIsDemo) return "演示数据";
  if (gameSource === "official") return "官方线上 API · 真实事件";
  if (gameSource === "adversarial") return "真实 run · 本地 generator 难例";
  if (gameSource === "handwritten") return "真实 run · 本地 SDK 游戏";
  return "真实 API run";
}

function gridShape(grid?: Grid): string {
  if (!grid?.length) return "--";
  const cols = grid.reduce((max, row) => Math.max(max, row.length), 0);
  return `${cols} x ${grid.length}`;
}

function normalizeHint(hint?: string): string {
  switch (hint) {
    case "arrow_up":
      return "↑";
    case "arrow_down":
      return "↓";
    case "arrow_left":
      return "←";
    case "arrow_right":
      return "→";
    case "star":
      return "*";
    default:
      return "?";
  }
}

function hintLabel(hint?: string): string {
  switch (hint) {
    case "arrow_up":
      return "提示上";
    case "arrow_down":
      return "提示下";
    case "arrow_left":
      return "提示左";
    case "arrow_right":
      return "提示右";
    case "star":
      return "提示星标";
    default:
      return hint ?? "无提示";
  }
}

function programToMath(program: unknown): string {
  if (!program || typeof program !== "object") return "unknown";
  const prog = program as Record<string, unknown>;
  const op = String(prog.op ?? "");
  if (op === "identity") return "I";
  if (op === "translate") return `T(${Number(prog.dx ?? 0)},${Number(prog.dy ?? 0)})`;
  if (op === "rotate") return `R_${Number(prog.k ?? 0)}`;
  if (op === "reflect") return `M_${String(prog.axis ?? "?")}`;
  if (op === "conjugate") return `${programToMath(prog.g)} o ${programToMath(prog.f)} o ${programToMath(prog.g)}^-1`;
  if (op === "conditional") return `if ${describePredicate(prog.pred)} then ${programToMath(prog.then)} else ${programToMath(prog.else)}`;
  if (op === "compose" && Array.isArray(prog.fs)) return prog.fs.map(programToMath).join(" o ");
  return op || "unknown";
}

function describePredicate(predicate: unknown): string {
  if (!predicate || typeof predicate !== "object") return "condition";
  const pred = predicate as Record<string, unknown>;
  switch (pred.pred) {
    case "in_region":
      return `区域 x${pred.x0}-${pred.x1},y${pred.y0}-${pred.y1}`;
    case "agent_color":
      return `agent 颜色=${pred.c}`;
    case "tile_under":
      return `脚下 tile=${pred.t}`;
    case "step_mod":
      return `step%${pred.k}=${pred.r}`;
    case "regime_is":
      return `regime=${pred.i}`;
    default:
      return String(pred.pred ?? "condition");
  }
}

function vectorLabel(dx: number, dy: number): string {
  if (dx === 0 && dy === -1) return "上移 1 格";
  if (dx === 0 && dy === 1) return "下移 1 格";
  if (dx === -1 && dy === 0) return "左移 1 格";
  if (dx === 1 && dy === 0) return "右移 1 格";
  if (dx === 0 && dy === 0) return "不移动";
  return `移动 dx=${dx}, dy=${dy}`;
}

function describeProgram(program: unknown): string {
  if (!program || typeof program !== "object") return "未知语义";
  const prog = program as Record<string, unknown>;
  const op = String(prog.op ?? "");
  if (op === "translate") return vectorLabel(Number(prog.dx ?? 0), Number(prog.dy ?? 0));
  if (op === "identity") return "不改变状态";
  if (op === "conjugate") return `坐标变换后的 ${describeProgram(prog.f)}`;
  if (op === "conditional") return `${describePredicate(prog.pred)} 时 ${describeProgram(prog.then)}，否则 ${describeProgram(prog.else)}`;
  if (op === "compose" && Array.isArray(prog.fs)) return prog.fs.map(describeProgram).join("，然后 ");
  if (op === "rotate") return `旋转坐标 R_${Number(prog.k ?? 0)}`;
  if (op === "reflect") return `镜像坐标 M_${String(prog.axis ?? "?")}`;
  return programToMath(program);
}

function trapLabel(trap: string): string {
  const labels: Record<string, string> = {
    permute: "打乱按钮与真实方向",
    conjugate_mirror: "镜像坐标系下移动",
    conjugate_rotate: "旋转坐标系下移动",
    diagonal: "某个动作变成斜向",
    region_split: "不同区域动作含义不同",
    color_state: "agent 颜色改变动作含义",
    regime_switch: "踩开关后动作表切换",
    decoy_hint: "箭头提示故意误导",
    wall_ambiguity: "墙体让动作效果难辨认",
    long_jump: "动作可能跨两格"
  };
  return labels[trap] ?? trap;
}

function eventTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    episode_start: "开局",
    observation: "状态",
    hypotheses: "假设",
    plan: "计划",
    prediction: "预测",
    action_taken: "执行",
    outcome: "反馈",
    belief_revision: "修正",
    episode_end: "终局",
    generator_update: "生成器更新"
  };
  return labels[type] ?? type;
}

function topHypothesisFor(actionName: string | undefined, hypotheses: ActionHypotheses[]): HypothesisItem | undefined {
  if (!actionName) return undefined;
  return hypotheses.find((item) => item.action === actionName)?.items[0];
}

function resultLabel(result?: string): string {
  switch (result) {
    case "win":
      return "胜利";
    case "lose":
      return "失败";
    case "timeout":
      return "超时";
    case undefined:
    case "":
      return "未知";
    default:
      return result;
  }
}

function resultTone(result?: string): "win" | "lose" | "timeout" | "running" {
  if (result === "win") return "win";
  if (result === "timeout") return "timeout";
  if (result === "lose") return "lose";
  return "running";
}

function isTerminalResult(result?: string): boolean {
  return result === "win" || result === "lose" || result === "timeout";
}

function ConfGauge({ value }: { value?: number }) {
  const numeric = Math.max(0, Math.min(1, value ?? 0));
  return (
    <div className="conf-gauge" style={{ "--conf": `${numeric * 100}%` } as React.CSSProperties}>
      <strong>{pct(value)}</strong>
      <span>预测置信度</span>
    </div>
  );
}

function GameStatusPanel({
  selectedEpisode,
  episodeEnd,
  currentStep,
  maxStep,
  live,
  streamState
}: {
  selectedEpisode?: EpisodeSummary;
  episodeEnd?: { result: string; steps: number };
  currentStep: number;
  maxStep: number;
  live: boolean;
  streamState: string;
}) {
  const result = episodeEnd?.result ?? selectedEpisode?.result;
  const terminalStep = episodeEnd?.steps ?? selectedEpisode?.steps ?? maxStep;
  const ended = Boolean(episodeEnd) || isTerminalResult(result);
  const tone = ended ? resultTone(result) : "running";
  const showingHistory = ended && currentStep < terminalStep;

  return (
    <section className={`game-status-panel game-status-${tone}`}>
      <div className="game-status-main">
        <span>游戏状态</span>
        <strong>{ended ? `已结束：${resultLabel(result)}` : "进行中"}</strong>
        <small>
          {showingHistory
            ? `当前显示历史第 ${currentStep} 步，终局在第 ${terminalStep} 步`
            : ended
              ? `当前显示终局第 ${terminalStep} 步`
              : `当前显示最新第 ${currentStep} 步`}
        </small>
      </div>
      <dl className="status-facts">
        <div>
          <dt>当前回放</dt>
          <dd>{live ? "最新" : `历史 step ${currentStep}`}</dd>
        </div>
        <div>
          <dt>终局/最新</dt>
          <dd>{ended ? `step ${terminalStep}` : `step ${maxStep}`}</dd>
        </div>
        <div>
          <dt>episode</dt>
          <dd>{selectedEpisode?.id ?? "--"}</dd>
        </div>
        <div>
          <dt>game_id</dt>
          <dd>{selectedEpisode?.game_id ?? "--"}</dd>
        </div>
        <div>
          <dt>事件流</dt>
          <dd>{streamLabel(streamState)}</dd>
        </div>
      </dl>
    </section>
  );
}

type PipelineStageId = "source" | "state" | "actions" | "decision" | "feedback" | "raw";

function PipelineStagePanel({
  index,
  title,
  summary,
  stage,
  activeStage,
  children,
  className = ""
}: {
  index: number;
  title: string;
  summary: string;
  stage: PipelineStageId;
  activeStage: PipelineStageId;
  children: React.ReactNode;
  className?: string;
}) {
  const active = stage === activeStage;
  return (
    <section className={`pipeline-stage-panel ${className} ${active ? "stage-active" : ""}`}>
      <header className="stage-header">
        <span className="stage-index">{index}</span>
        <div>
          <h3>{title}</h3>
          <p>{summary}</p>
        </div>
        {active ? <strong>当前阶段</strong> : null}
      </header>
      {children}
    </section>
  );
}

function SourceStageContent({
  selectedRun,
  dataSource,
  streamState,
  streamIsDemo,
  spec,
  observation,
  eventCount
}: {
  selectedRun?: RunSummary;
  dataSource: "api" | "demo";
  streamState: string;
  streamIsDemo: boolean;
  spec?: GameSpec;
  observation?: ObservationPayload;
  eventCount: number;
}) {
  const gameSource = String(selectedRun?.config?.game_source ?? spec?.meta?.source ?? "");
  const isMock = dataSource === "demo" || streamIsDemo;
  const onlineState =
    gameSource === "official"
      ? `guid ${observation?.guid ?? spec?.meta?.guid ?? "--"}`
      : `seed ${selectedRun?.config?.seed ?? spec?.meta?.seed ?? "--"}`;
  const traps = spec?.meta?.traps ?? [];
  const sourceNote =
    gameSource === "adversarial"
      ? "run 开始时生成；回放只读已写入事件。"
      : gameSource === "official"
        ? "适配器连接官方环境；仅显示已暴露状态。"
        : gameSource === "handwritten"
          ? "本地 SDK 游戏；事件来自真实运行。"
          : "按事件流显示。";

  return (
    <div className="source-stage-content">
      <div className={`source-verdict ${isMock ? "source-verdict-demo" : ""}`}>
        <span>{isMock ? "MOCK" : "REAL"}</span>
        <strong>{sourceVerdict(dataSource, streamIsDemo, gameSource)}</strong>
        <p>{sourceNote}</p>
      </div>
      <dl className="source-facts">
        <div>
          <dt>数据通道</dt>
          <dd>{isMock ? "demoData.ts" : `API + ${streamLabel(streamState)}`}</dd>
        </div>
        <div>
          <dt>游戏来源</dt>
          <dd>{sourceLabel(gameSource)}</dd>
        </div>
        <div>
          <dt>运行标识</dt>
          <dd>{selectedRun?.id ?? "--"}</dd>
        </div>
        <div>
          <dt>状态尺寸</dt>
          <dd>{gridShape(observation?.grid)}</dd>
        </div>
        <div>
          <dt>事件数</dt>
          <dd>{eventCount}</dd>
        </div>
        <div>
          <dt>线上/本地</dt>
          <dd>{onlineState}</dd>
        </div>
      </dl>
      {traps.length ? (
        <div className="trap-list">
          {traps.map((trap) => (
            <span key={trap}>{trapLabel(trap)}</span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function ActionSpacePanel({
  actions,
  hypotheses,
  selectedAction,
  observation
}: {
  actions?: Record<string, GameAction>;
  hypotheses: ActionHypotheses[];
  selectedAction?: string;
  observation?: ObservationPayload;
}) {
  const explicitRows = Object.entries(actions ?? {});
  const availableRows = (observation?.available_actions ?? []).map(
    (actionId) => [String(actionId), {} as GameAction] as [string, GameAction]
  );
  const rows = explicitRows.length ? explicitRows : availableRows;
  return (
    <section className="action-space-panel">
      <div className="panel-subhead compact-subhead">
        <h3>动作空间</h3>
        <span>{rows.length} 个可用动作</span>
      </div>
      <div className="action-space-table" role="table" aria-label="Action space">
        {rows.map(([name, config]) => {
          const top = topHypothesisFor(name, hypotheses);
          return (
            <div className={`action-space-row ${name === selectedAction ? "active" : ""}`} role="row" key={name}>
              <div className="action-id" role="cell">
                <strong>{name}</strong>
                <span>{normalizeHint(config.hint)}</span>
              </div>
              <div role="cell">
                <small>提示</small>
                <span>{hintLabel(config.hint)}</span>
              </div>
              <div role="cell">
                <small>真实语义</small>
                <span>
                  {config.program ? (
                    <>
                      {describeProgram(config.program)} <code>{programToMath(config.program)}</code>
                    </>
                  ) : (
                    "官方环境未暴露 DSL，按 action id 回放"
                  )}
                </span>
              </div>
              <div role="cell">
                <small>agent 猜测</small>
                <span>{top ? `${top.math} / ${pct(top.prob)}` : "--"}</span>
              </div>
            </div>
          );
        })}
      </div>
      {!rows.length ? <div className="empty-panel">这一步没有返回可用动作列表。</div> : null}
    </section>
  );
}

function TraceEvent({ event }: { event: ArcEvent }) {
  return (
    <details className="trace-event">
      <summary>
        <span>{event.type}</span>
        <small>step {event.step_idx}</small>
      </summary>
      <pre>{formatJson(event.payload)}</pre>
    </details>
  );
}

function DecisionTrace({
  events,
  observation,
  plan,
  prediction,
  action,
  outcome,
  revisions,
  caption
}: {
  events: ArcEvent[];
  observation?: ObservationPayload;
  plan?: PlanPayload;
  prediction?: { action: string; predicted_grid: Grid; conf: number; math?: string };
  action?: { action: string; intent: string };
  outcome?: { correct: boolean; match_ratio: number; surprise: number };
  revisions: BeliefRevisionPayload[];
  caption?: string;
}) {
  const rows = [
    {
      label: "1 观察",
      value: observation ? `${gridShape(observation.grid)} / step ${observation.step_idx ?? "--"}` : "没有 observation"
    },
    {
      label: "2 假设",
      value: `${events.filter((event) => event.type === "hypotheses").length} 条 hypotheses 事件`
    },
    {
      label: "3 计划",
      value: plan ? `${plan.intent} -> ${plan.actions.join(" -> ") || "--"} / risk ${pct(plan.risk)}` : "没有 plan"
    },
    {
      label: "4 预测",
      value: prediction ? `${prediction.action} / conf ${pct(prediction.conf)} / ${prediction.math ?? "--"}` : "没有 prediction"
    },
    {
      label: "5 执行",
      value: action ? `${action.action} / ${action.intent}` : "没有 action_taken"
    },
    {
      label: "6 结果",
      value: outcome
        ? `${outcome.correct ? "预测正确" : "预测错误"} / match ${pct(outcome.match_ratio)} / surprise ${pct(outcome.surprise)}`
        : "没有 outcome"
    },
    {
      label: "7 修正",
      value: revisions.length ? revisions.map((revision) => `${revision.action}: ${revision.trigger}`).join(", ") : "无信念修正"
    }
  ];

  return (
    <section className="decision-trace">
      <div className="panel-subhead">
        <h3>完整决策过程</h3>
        <span>{caption ?? `${events.length} 条原始事件`}</span>
      </div>
      <ol className="decision-steps">
        {rows.map((row) => (
          <li key={row.label}>
            <strong>{row.label}</strong>
            <span>{row.value}</span>
          </li>
        ))}
      </ol>
      <div className="trace-events">
        {events.map((event, index) => (
          <TraceEvent event={event} key={`${event.id ?? index}-${event.type}`} />
        ))}
      </div>
    </section>
  );
}

function DecisionStepNotice({
  currentStep,
  decisionStep,
  onJump
}: {
  currentStep: number;
  decisionStep: number;
  onJump: () => void;
}) {
  return (
    <div className="decision-step-notice">
      <div>
        <strong>终局 step {currentStep} 只有结束事件</strong>
        <span>这里展示的是终局前最后一次真实决策 step {decisionStep}。</span>
      </div>
      <button type="button" onClick={onJump}>
        跳到 step {decisionStep}
      </button>
    </div>
  );
}

function RawStatePanel({
  selectedRun,
  spec,
  observation,
  stepEvents
}: {
  selectedRun?: RunSummary;
  spec?: GameSpec;
  observation?: ObservationPayload;
  stepEvents: ArcEvent[];
}) {
  const statePayload = {
    run_config: selectedRun?.config ?? {},
    game_spec: spec ?? {},
    current_observation: observation ?? {},
    events_this_step: stepEvents
  };

  return (
    <section className="raw-state-panel">
      <div className="panel-subhead">
        <h3>完整游戏状态</h3>
        <span>真实事件 payload</span>
      </div>
      <details open>
        <summary>当前 observation</summary>
        <pre>{formatJson(observation)}</pre>
      </details>
      <details>
        <summary>run / spec / step events</summary>
        <pre>{formatJson(statePayload)}</pre>
      </details>
    </section>
  );
}

function changeFor(item: HypothesisItem, previous?: ActionHypotheses): "up" | "down" | "flat" {
  const prior = previous?.items.find((candidate) => candidate.math === item.math)?.prob;
  if (prior === undefined) return "flat";
  if (item.prob > prior + 0.02) return "up";
  if (item.prob < prior - 0.02) return "down";
  return "flat";
}

function HypothesisCard({
  hypothesis,
  previous,
  revision,
  actualProgram
}: {
  hypothesis: ActionHypotheses;
  previous?: ActionHypotheses;
  revision?: BeliefRevisionPayload;
  actualProgram?: unknown;
}) {
  return (
    <article className={`hypothesis-card ${revision ? "hypothesis-revision" : ""}`}>
      <header>
        <div>
          <strong>{hypothesis.action}</strong>
          <small>真实：{actualProgram ? programToMath(actualProgram) : "--"}</small>
        </div>
        {revision ? <span>信念修正：{revision.trigger}</span> : null}
      </header>
      <div className="hypothesis-list">
        {hypothesis.items.slice(0, 3).map((item) => {
          const change = changeFor(item, previous);
          return (
            <div className="hypothesis-row" key={`${hypothesis.action}-${item.math}`}>
              <div>
                <span className="hypothesis-label">agent 猜测</span>
                <code>{item.math}</code>
                <span className={`delta delta-${change}`}>
                  {change === "up" ? "上升" : change === "down" ? "下降" : "持平"}
                </span>
              </div>
              <div className="prob-bar" aria-label={`${Math.round(item.prob * 100)} percent`}>
                <span style={{ width: `${Math.max(3, item.prob * 100)}%` }} />
              </div>
              <em>{pct(item.prob)}</em>
            </div>
          );
        })}
      </div>
      {revision ? (
        <footer>
          旧猜测 {revision.old_top} {"->"} 新猜测 {revision.new_top ?? "已重算"}；重新枚举 {revision.new_candidates_count} 个候选
        </footer>
      ) : null}
    </article>
  );
}

function ImaginePanel({
  baseGrid,
  plan,
  predicted,
  actual,
  correct,
  confidence
}: {
  baseGrid?: Grid;
  plan?: PlanPayload;
  predicted?: Grid;
  actual?: Grid;
  correct?: boolean;
  confidence?: number;
}) {
  return (
    <section className="imagine-panel">
      <div className="panel-subhead">
        <h3>脑内推演</h3>
        <span>路径可信度 {pct(plan?.risk)}</span>
      </div>
      <GridCanvas grid={baseGrid} overlay={{ ghostGrids: plan?.imagined_grids }} label="半透明格子是计划中的后续状态" />

      <div className="panel-subhead">
        <h3>预测检查</h3>
        <span className={`result ${correct ? "result-win" : correct === false ? "result-lose" : ""}`}>
          {correct === undefined ? "等待结果" : correct ? "预测正确" : "预测错误"}
        </span>
      </div>
      <div className="prediction-grid">
        <GridCanvas
          grid={actual ?? baseGrid}
          overlay={{ predictedGrid: predicted, actualGrid: actual, showDiff: Boolean(predicted && actual) }}
          label="Diff heatmap"
        />
        <ConfGauge value={confidence} />
      </div>
    </section>
  );
}

function TerminalOutcomeCard({
  episodeEnd,
  selectedEpisode
}: {
  episodeEnd?: {
    result: string;
    steps: number;
    avg_conf?: number;
    overconf?: number;
    probe_steps?: number;
    revisions?: number;
  };
  selectedEpisode?: EpisodeSummary;
}) {
  const result = episodeEnd?.result ?? selectedEpisode?.result;
  const steps = episodeEnd?.steps ?? selectedEpisode?.steps;
  const avgConf = episodeEnd?.avg_conf ?? selectedEpisode?.avg_conf;
  const overconf = episodeEnd?.overconf ?? selectedEpisode?.overconf;
  const probeSteps = episodeEnd?.probe_steps ?? selectedEpisode?.probe_steps;
  const revisions = episodeEnd?.revisions ?? selectedEpisode?.revisions;

  return (
    <div className={`terminal-outcome terminal-outcome-${resultTone(result)}`}>
      <strong>episode_end：{resultLabel(result)}</strong>
      <dl>
        <div>
          <dt>终局 step</dt>
          <dd>{steps ?? "--"}</dd>
        </div>
        <div>
          <dt>平均置信度</dt>
          <dd>{pct(avgConf)}</dd>
        </div>
        <div>
          <dt>过度自信</dt>
          <dd>{pct(overconf)}</dd>
        </div>
        <div>
          <dt>探针步</dt>
          <dd>{probeSteps ?? 0}</dd>
        </div>
        <div>
          <dt>修正次数</dt>
          <dd>{revisions ?? 0}</dd>
        </div>
      </dl>
    </div>
  );
}

function Timeline({
  steps,
  currentStep,
  terminalStep,
  ended,
  onScrub
}: {
  steps: ReturnType<typeof buildTimeline>;
  currentStep: number;
  terminalStep: number;
  ended: boolean;
  onScrub: (step: number) => void;
}) {
  return (
    <div className="timeline" role="list" aria-label="Episode timeline">
      {steps.map((step) => {
        const terminal = ended && step.step === terminalStep;
        const eventSummary = step.eventTypes.map(eventTypeLabel).join(" / ") || "无事件";
        return (
          <button
            key={step.step}
            type="button"
            className={[
              "timeline-dot",
              step.step === currentStep ? "active" : "",
              step.intent === "probe" ? "probe" : "goal",
              step.surprise > 0.5 ? "surprise" : "",
              step.hasRevision ? "revision" : "",
              terminal ? "terminal" : ""
            ].join(" ")}
            title={`${terminal ? "终局 " : ""}step ${step.step}: ${eventSummary}`}
            onClick={() => onScrub(step.step)}
          >
            <span>{step.step}</span>
          </button>
        );
      })}
      <div className="timeline-legend" aria-hidden="true">
        <span>圆点：目标执行</span>
        <span>方块：实验探针</span>
        <span>红边：信念修正</span>
        <span>粗边：终局</span>
      </div>
    </div>
  );
}

function StepEventSummary({
  currentStep,
  events,
  decisionStep
}: {
  currentStep: number;
  events: ArcEvent[];
  decisionStep?: number;
}) {
  const types = events.map((event) => event.type);
  return (
    <div className="step-event-summary">
      <strong>step {currentStep} 事件</strong>
      <div>
        {types.length ? (
          types.map((type, index) => <span key={`${type}-${index}`}>{eventTypeLabel(type)}</span>)
        ) : (
          <span>无事件</span>
        )}
      </div>
      {decisionStep !== undefined && decisionStep !== currentStep ? <small>决策阶段显示 step {decisionStep}</small> : null}
    </div>
  );
}

function ReplayController({
  maxStep,
  currentStep,
  live,
  speed,
  onStep,
  onLive,
  onSpeed
}: {
  maxStep: number;
  currentStep: number;
  live: boolean;
  speed: number;
  onStep: (step: number) => void;
  onLive: () => void;
  onSpeed: (speed: number) => void;
}) {
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!playing) return;
    const interval = window.setInterval(() => {
      onStep(currentStep >= maxStep ? 0 : currentStep + 1);
    }, speed);
    return () => window.clearInterval(interval);
  }, [currentStep, maxStep, onStep, playing, speed]);

  return (
    <div className="replay-controller">
      <button type="button" onClick={() => onStep(Math.max(0, currentStep - 1))}>
        上一步
      </button>
      <button type="button" onClick={() => setPlaying((value) => !value)}>
        {playing ? "暂停" : "播放"}
      </button>
      <button type="button" onClick={() => onStep(Math.min(maxStep, currentStep + 1))}>
        下一步
      </button>
      <label>
        速度
        <select value={speed} onChange={(event) => onSpeed(Number(event.target.value))}>
          <option value={1200}>0.5x</option>
          <option value={700}>1x</option>
          <option value={350}>2x</option>
        </select>
      </label>
      <button type="button" className={live ? "live-button active" : "live-button"} onClick={onLive}>
        回到最新
      </button>
    </div>
  );
}

export function EpisodeViewer({ runId, selectedRun, dataSource, onDemo }: EpisodeViewerProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const [episodes, setEpisodes] = useState<EpisodeSummary[]>(() => (runId ? [] : demoEpisodes));
  const requestedEpisode = searchParams.get("episode");
  const requestedStep = searchParams.get("step");
  const requestedEpisodeInRun = requestedEpisode ? episodes.some((episode) => episode.id === requestedEpisode) : false;
  const selectedEpisodeId: string | undefined = requestedEpisodeInRun && requestedEpisode ? requestedEpisode : episodes[0]?.id;
  const [currentStep, setCurrentStep] = useState(Number(requestedStep ?? 0));
  const [live, setLive] = useState(!requestedStep);
  const [speed, setSpeed] = useState(700);
  const stream = useRunStream(runId, selectedEpisodeId);

  useEffect(() => {
    let cancelled = false;
    async function loadEpisodes() {
      if (!runId) {
        setEpisodes(demoEpisodes);
        return;
      }
      setEpisodes([]);
      try {
        const rows = await api.getEpisodes(runId, 100, 0);
        if (!cancelled) setEpisodes(rows);
      } catch {
        if (!cancelled) {
          setEpisodes(demoEpisodes);
          onDemo();
        }
      }
    }
    void loadEpisodes();
    return () => {
      cancelled = true;
    };
  }, [onDemo, runId]);

  const maxStep = useMemo(() => getLastDecisionStep(stream.events), [stream.events]);
  const spec = useMemo(() => getGameSpec(stream.events), [stream.events]);
  const baseGrid = useMemo(() => getObservationAtStep(stream.events, currentStep), [currentStep, stream.events]);
  const observation = useMemo(() => getObservationPayloadAtStep(stream.events, currentStep), [currentStep, stream.events]);
  const hypotheses = useMemo(() => getHypothesesAtStep(stream.events, currentStep), [currentStep, stream.events]);
  const previousHypotheses = useMemo(() => getPreviousHypotheses(stream.events, currentStep), [currentStep, stream.events]);
  const revisions = useMemo(() => getRevisionsAtStep(stream.events, currentStep), [currentStep, stream.events]);
  const plan = useMemo(() => getPlanAtStep(stream.events, currentStep), [currentStep, stream.events]);
  const prediction = useMemo(() => getPredictionAtStep(stream.events, currentStep), [currentStep, stream.events]);
  const outcome = useMemo(() => getOutcomeAtStep(stream.events, currentStep), [currentStep, stream.events]);
  const action = useMemo(() => getActionAtStep(stream.events, currentStep), [currentStep, stream.events]);
  const timeline = useMemo(() => buildTimeline(stream.events), [stream.events]);
  const episodeEnd = useMemo(() => getEpisodeEnd(stream.events), [stream.events]);
  const stepEvents = useMemo(() => getEventsAtStep(stream.events, currentStep), [currentStep, stream.events]);
  const selectedEpisode = useMemo(
    () => episodes.find((episode) => episode.id === selectedEpisodeId),
    [episodes, selectedEpisodeId]
  );
  const episodeResult = episodeEnd?.result ?? selectedEpisode?.result;
  const terminalStep = episodeEnd?.steps ?? selectedEpisode?.steps ?? maxStep;
  const episodeEnded = Boolean(episodeEnd) || isTerminalResult(episodeResult);
  const replayMaxStep = Math.max(maxStep, terminalStep);
  const gameSource = String(selectedRun?.config?.game_source ?? spec?.meta?.source ?? "");
  const showStepFeedback = Boolean(plan || prediction || outcome || !episodeEnded || currentStep < terminalStep);
  const decisionDisplayStep = episodeEnded && currentStep >= terminalStep && maxStep < terminalStep ? maxStep : currentStep;
  const decisionObservation = useMemo(
    () => getObservationPayloadAtStep(stream.events, decisionDisplayStep),
    [decisionDisplayStep, stream.events]
  );
  const decisionHypotheses = useMemo(
    () => getHypothesesAtStep(stream.events, decisionDisplayStep),
    [decisionDisplayStep, stream.events]
  );
  const previousDecisionHypotheses = useMemo(
    () => getPreviousHypotheses(stream.events, decisionDisplayStep),
    [decisionDisplayStep, stream.events]
  );
  const decisionRevisions = useMemo(
    () => getRevisionsAtStep(stream.events, decisionDisplayStep),
    [decisionDisplayStep, stream.events]
  );
  const decisionPlan = useMemo(() => getPlanAtStep(stream.events, decisionDisplayStep), [decisionDisplayStep, stream.events]);
  const decisionPrediction = useMemo(
    () => getPredictionAtStep(stream.events, decisionDisplayStep),
    [decisionDisplayStep, stream.events]
  );
  const decisionOutcome = useMemo(
    () => getOutcomeAtStep(stream.events, decisionDisplayStep),
    [decisionDisplayStep, stream.events]
  );
  const decisionAction = useMemo(() => getActionAtStep(stream.events, decisionDisplayStep), [decisionDisplayStep, stream.events]);
  const decisionStepEvents = useMemo(() => getEventsAtStep(stream.events, decisionDisplayStep), [decisionDisplayStep, stream.events]);
  const showingBorrowedDecision = decisionDisplayStep !== currentStep;
  const activeStage: PipelineStageId =
    episodeEnded && currentStep >= terminalStep
      ? "feedback"
      : revisions.length > 0 || outcome || action || prediction
      ? "feedback"
      : plan || hypotheses.length
        ? "decision"
        : spec?.actions || observation?.available_actions?.length
          ? "actions"
          : observation
            ? "state"
            : "source";

  useEffect(() => {
    if (live) setCurrentStep(replayMaxStep);
  }, [live, replayMaxStep]);

  useEffect(() => {
    if (stream.isDemo) onDemo();
  }, [onDemo, stream.isDemo]);

  function setStep(step: number) {
    if (!selectedEpisodeId) return;
    setLive(false);
    setCurrentStep(step);
    setSearchParams((params) => {
      params.set("episode", selectedEpisodeId);
      params.set("step", String(step));
      return params;
    });
  }

  function selectEpisode(episodeId: string) {
    if (!episodeId) return;
    setLive(true);
    setCurrentStep(0);
    navigate(`/episode?episode=${encodeURIComponent(episodeId)}`);
  }

  return (
    <div className="view-stack episode-view">
      <div className="view-heading">
        <div>
          <h2>对局回放</h2>
          <p>来源、状态、动作、信念、反馈、原始事件，一条线看完。</p>
        </div>
        <div className="episode-select">
          <label>
            对局
            <select
              value={selectedEpisodeId ?? ""}
              disabled={!episodes.length}
              onChange={(event) => selectEpisode(event.target.value)}
            >
              {!episodes.length ? <option value="">等待第一局</option> : null}
              {episodes.map((episode) => (
                <option value={episode.id} key={episode.id}>
                  #{episode.idx} {episode.game_id}
                </option>
              ))}
            </select>
          </label>
          <span className={`inline-status status-${stream.state}`}>{streamLabel(stream.state)}</span>
        </div>
      </div>

      <GameStatusPanel
        selectedEpisode={selectedEpisode}
        episodeEnd={episodeEnd}
        currentStep={currentStep}
        maxStep={replayMaxStep}
        live={live}
        streamState={stream.state}
      />

      {!selectedEpisodeId ? (
        <section className="replay-empty-state">
          <h3>等待训练产生第一局</h3>
          <p>当前 run 已创建，但还没有 episode 写入 API 数据库。左侧训练进度开始增长后，这里会自动切到真实事件流。</p>
        </section>
      ) : (
        <>
          <section className="pipeline-workbench" aria-label="Episode pipeline workbench">
            <div className="pipeline-main-flow">
              <PipelineStagePanel
                index={1}
                title="来源与生成"
                summary={`${sourceLabel(gameSource)} · ${dataSource === "demo" || stream.isDemo ? "mock" : "real"}`}
                stage="source"
                activeStage={activeStage}
                className="source-stage"
              >
                <SourceStageContent
                  selectedRun={selectedRun}
                  dataSource={dataSource}
                  streamState={stream.state}
                  streamIsDemo={stream.isDemo}
                  spec={spec}
                  observation={observation}
                  eventCount={stream.events.length}
                />
              </PipelineStagePanel>

              <PipelineStagePanel
                index={3}
                title="动作空间"
                summary="action 不是提示箭头"
                stage="actions"
                activeStage={activeStage}
                className="actions-stage"
              >
                <ActionSpacePanel
                  actions={spec?.actions}
                  hypotheses={hypotheses}
                  selectedAction={decisionAction?.action ?? decisionPrediction?.action ?? action?.action ?? prediction?.action}
                  observation={observation}
                />
              </PipelineStagePanel>

              <PipelineStagePanel
                index={4}
                title="信念与决策"
                summary={
                  decisionPlan
                    ? `step ${decisionDisplayStep}: ${decisionPlan.intent} / ${decisionPlan.actions.join(" -> ") || "--"}`
                    : `step ${decisionDisplayStep}: ${decisionHypotheses.length} 个动作假设`
                }
                stage="decision"
                activeStage={activeStage}
                className="decision-stage"
              >
                {showingBorrowedDecision ? (
                  <DecisionStepNotice currentStep={currentStep} decisionStep={decisionDisplayStep} onJump={() => setStep(decisionDisplayStep)} />
                ) : null}
                <DecisionTrace
                  events={decisionStepEvents}
                  observation={decisionObservation}
                  plan={decisionPlan}
                  prediction={decisionPrediction}
                  action={decisionAction}
                  outcome={decisionOutcome}
                  revisions={decisionRevisions}
                  caption={`step ${decisionDisplayStep} · ${decisionStepEvents.length} 条原始事件`}
                />
                <div className="panel-subhead hypothesis-head">
                  <h3>动作语义猜测</h3>
                  <span>step {decisionDisplayStep} · {decisionHypotheses.length} 个动作</span>
                </div>
                <div className="hypothesis-stack">
                  {decisionHypotheses.map((hypothesis) => (
                    <HypothesisCard
                      key={hypothesis.action}
                      hypothesis={hypothesis}
                      previous={previousDecisionHypotheses.find((item) => item.action === hypothesis.action)}
                      revision={decisionRevisions.find((revision) => revision.action === hypothesis.action)}
                      actualProgram={spec?.actions?.[hypothesis.action]?.program}
                    />
                  ))}
                  {!decisionHypotheses.length ? (
                    <div className="empty-panel">这一步没有假设事件。官方真实游戏目前只回放 frame，不伪造本地 DSL 假设。</div>
                  ) : null}
                </div>
              </PipelineStagePanel>

              <PipelineStagePanel
                index={5}
                title="预测与反馈"
                summary={
                  episodeEnded && currentStep >= terminalStep
                    ? `episode_end: ${resultLabel(episodeResult)} / step ${terminalStep}`
                    : outcome
                    ? `${outcome.correct ? "预测正确" : "预测错误"} / surprise ${pct(outcome.surprise)}`
                    : prediction
                      ? `${prediction.action} / conf ${pct(prediction.conf)}`
                      : "等待 prediction/outcome"
                }
                stage="feedback"
                activeStage={activeStage}
                className="feedback-stage"
              >
                {episodeEnded && currentStep >= terminalStep ? (
                  <TerminalOutcomeCard episodeEnd={episodeEnd} selectedEpisode={selectedEpisode} />
                ) : null}
                {showStepFeedback ? (
                  <ImaginePanel
                    baseGrid={baseGrid}
                    plan={plan}
                    predicted={prediction?.predicted_grid}
                    actual={outcome?.actual_grid}
                    correct={outcome?.correct}
                    confidence={prediction?.conf}
                  />
                ) : null}
              </PipelineStagePanel>
            </div>

            <aside className="pipeline-inspector" aria-label="Episode inspector">
              <PipelineStagePanel
                index={2}
                title="环境状态"
                summary={`step ${currentStep} / ${episodeEnded ? `终局 ${resultLabel(episodeResult)}` : "进行中"}`}
                stage="state"
                activeStage={activeStage}
                className="state-stage"
              >
                <GridCanvas grid={baseGrid} label={`当前显示第 ${currentStep} 步`} />
                <dl className="episode-facts">
                  <div>
                    <dt>当前步骤</dt>
                    <dd>{currentStep}</dd>
                  </div>
                  <div>
                    <dt>终局/最新</dt>
                    <dd>{episodeEnded ? terminalStep : replayMaxStep}</dd>
                  </div>
                  <div>
                    <dt>本步动作</dt>
                    <dd>{action?.action ?? "--"}</dd>
                  </div>
                  <div>
                    <dt>本局结果</dt>
                    <dd className={`result-text result-text-${resultTone(episodeResult)}`}>
                      {episodeEnded ? resultLabel(episodeResult) : "进行中"}
                    </dd>
                  </div>
                </dl>
              </PipelineStagePanel>

              <PipelineStagePanel
                index={6}
                title="完整事件与状态"
                summary={`${stepEvents.length} 条本步事件 / ${stream.events.length} 条总事件`}
                stage="raw"
                activeStage={activeStage}
                className="raw-stage"
              >
                <RawStatePanel selectedRun={selectedRun} spec={spec} observation={observation} stepEvents={stepEvents} />
              </PipelineStagePanel>
            </aside>
          </section>

          <section className="timeline-panel pipeline-history-panel">
            <div className="panel-subhead">
              <h3>7 历史回放</h3>
              <span>
                {episodeEnded
                  ? `本局已结束：${resultLabel(episodeResult)}，终局 step ${terminalStep}`
                  : `本局进行中，最新 step ${replayMaxStep}`}
              </span>
            </div>
            <Timeline
              steps={timeline}
              currentStep={currentStep}
              terminalStep={terminalStep}
              ended={episodeEnded}
              onScrub={setStep}
            />
            <StepEventSummary
              currentStep={currentStep}
              events={stepEvents}
              decisionStep={showingBorrowedDecision ? decisionDisplayStep : undefined}
            />
            <ReplayController
              maxStep={replayMaxStep}
              currentStep={currentStep}
              live={live}
              speed={speed}
              onStep={setStep}
              onSpeed={setSpeed}
              onLive={() => {
                setLive(true);
                setSearchParams((params) => {
                  params.set("episode", selectedEpisodeId);
                  params.delete("step");
                  return params;
                });
              }}
            />
          </section>
        </>
      )}
    </div>
  );
}
