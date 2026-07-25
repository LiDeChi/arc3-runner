import type {
  ActionHypotheses,
  ActionTakenPayload,
  ArcEvent,
  BeliefRevisionPayload,
  EpisodeEndPayload,
  EpisodeStartPayload,
  GameSpec,
  Grid,
  HypothesesPayload,
  ObservationPayload,
  OutcomePayload,
  PlanPayload,
  PredictionPayload
} from "./types";

export interface TimelineStep {
  step: number;
  intent?: string;
  surprise: number;
  hasRevision: boolean;
  correct?: boolean;
  eventTypes: string[];
}

export function sortEvents(events: ArcEvent[]): ArcEvent[] {
  return [...events].sort((a, b) => {
    if (a.step_idx !== b.step_idx) return a.step_idx - b.step_idx;
    return (a.id ?? 0) - (b.id ?? 0);
  });
}

export function uniqueEvents(events: ArcEvent[]): ArcEvent[] {
  const seen = new Set<string>();
  const output: ArcEvent[] = [];

  for (const event of sortEvents(events)) {
    const key =
      event.id !== undefined
        ? `id:${event.id}`
        : `${event.episode_id}:${event.step_idx}:${event.type}:${JSON.stringify(event.payload)}`;
    if (!seen.has(key)) {
      seen.add(key);
      output.push(event);
    }
  }

  return output;
}

export function getMaxStep(events: ArcEvent[]): number {
  return events.reduce((max, event) => Math.max(max, event.step_idx), 0);
}

export function getLastDecisionStep(events: ArcEvent[]): number {
  const decisionEvent = sortEvents(events)
    .filter((event) => ["plan", "prediction", "action_taken", "outcome", "belief_revision"].includes(event.type))
    .at(-1);
  return decisionEvent?.step_idx ?? getMaxStep(events);
}

export function getLatestEventId(events: ArcEvent[]): number | undefined {
  return events.reduce<number | undefined>((latest, event) => {
    if (event.id === undefined) return latest;
    return latest === undefined ? event.id : Math.max(latest, event.id);
  }, undefined);
}

export function getGameSpec(events: ArcEvent[]): GameSpec | undefined {
  const event = sortEvents(events).find((item) => item.type === "episode_start");
  return (event?.payload as EpisodeStartPayload | undefined)?.spec;
}

export function getObservationAtStep(events: ArcEvent[], step: number): Grid | undefined {
  const event = sortEvents(events)
    .filter((item) => item.type === "observation" && item.step_idx <= step)
    .at(-1);
  return (event?.payload as ObservationPayload | undefined)?.grid;
}

export function getObservationPayloadAtStep(events: ArcEvent[], step: number): ObservationPayload | undefined {
  const event = sortEvents(events)
    .filter((item) => item.type === "observation" && item.step_idx <= step)
    .at(-1);
  return event?.payload as ObservationPayload | undefined;
}

export function getObservationAtOrAfter(events: ArcEvent[], step: number): Grid | undefined {
  const exact = sortEvents(events).find((item) => item.type === "observation" && item.step_idx >= step);
  return (exact?.payload as ObservationPayload | undefined)?.grid ?? getObservationAtStep(events, step);
}

function latestPayloadAtStep<TPayload>(events: ArcEvent[], step: number, type: string): TPayload | undefined {
  const event = sortEvents(events)
    .filter((item) => item.type === type && item.step_idx <= step)
    .at(-1);
  return event?.payload as TPayload | undefined;
}

function exactPayloadAtStep<TPayload>(events: ArcEvent[], step: number, type: string): TPayload | undefined {
  const event = sortEvents(events)
    .filter((item) => item.type === type && item.step_idx === step)
    .at(-1);
  return event?.payload as TPayload | undefined;
}

export function getHypothesesAtStep(events: ArcEvent[], step: number): ActionHypotheses[] {
  const payload = latestPayloadAtStep<HypothesesPayload>(events, step, "hypotheses");
  return payload?.actions ?? payload?.hypotheses ?? [];
}

export function getPreviousHypotheses(events: ArcEvent[], step: number): ActionHypotheses[] {
  if (step <= 0) return [];
  const candidates = sortEvents(events).filter((event) => event.type === "hypotheses" && event.step_idx < step);
  const payload = candidates.at(-1)?.payload as HypothesesPayload | undefined;
  return payload?.actions ?? payload?.hypotheses ?? [];
}

export function getPlanAtStep(events: ArcEvent[], step: number): PlanPayload | undefined {
  return exactPayloadAtStep<PlanPayload>(events, step, "plan");
}

export function getPredictionAtStep(events: ArcEvent[], step: number): PredictionPayload | undefined {
  return exactPayloadAtStep<PredictionPayload>(events, step, "prediction");
}

export function getActionAtStep(events: ArcEvent[], step: number): ActionTakenPayload | undefined {
  return exactPayloadAtStep<ActionTakenPayload>(events, step, "action_taken");
}

export function getOutcomeAtStep(events: ArcEvent[], step: number): OutcomePayload | undefined {
  return exactPayloadAtStep<OutcomePayload>(events, step, "outcome");
}

export function getRevisionsAtStep(events: ArcEvent[], step: number): BeliefRevisionPayload[] {
  return sortEvents(events)
    .filter((event) => event.type === "belief_revision" && event.step_idx === step)
    .map((event) => event.payload as unknown as BeliefRevisionPayload);
}

export function getEventsAtStep(events: ArcEvent[], step: number): ArcEvent[] {
  return sortEvents(events).filter((event) => event.step_idx === step);
}

export function getEpisodeEnd(events: ArcEvent[]): EpisodeEndPayload | undefined {
  return sortEvents(events)
    .filter((event) => event.type === "episode_end")
    .at(-1)?.payload as EpisodeEndPayload | undefined;
}

export function buildTimeline(events: ArcEvent[]): TimelineStep[] {
  const maxStep = getMaxStep(events);

  return Array.from({ length: maxStep + 1 }, (_, step) => {
    const action = getActionAtStep(events, step);
    const outcome = getOutcomeAtStep(events, step);
    const revisions = getRevisionsAtStep(events, step);
    const eventTypes = getEventsAtStep(events, step).map((event) => event.type);
    return {
      step,
      intent: action?.intent,
      surprise: outcome?.surprise ?? 0,
      hasRevision: revisions.length > 0,
      correct: outcome?.correct,
      eventTypes
    };
  });
}

export function firstGridFromSpec(spec?: GameSpec): Grid | undefined {
  if (!spec) return undefined;
  const grid = spec.tiles.map((row) => [...row]);
  for (const entity of spec.entities ?? []) {
    if (grid[entity.y] && grid[entity.y][entity.x] !== undefined) {
      grid[entity.y][entity.x] = entity.color ?? 10;
    }
  }
  return grid;
}

export function latestEpisodeGrid(events: ArcEvent[]): Grid | undefined {
  return getObservationAtStep(events, getMaxStep(events)) ?? firstGridFromSpec(getGameSpec(events));
}

export function latestEpisodeTraps(events: ArcEvent[]): string[] {
  return getGameSpec(events)?.meta?.traps ?? [];
}
