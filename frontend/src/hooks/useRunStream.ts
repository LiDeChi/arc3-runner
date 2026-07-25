import { useEffect, useMemo, useState } from "react";
import { api, normalizeEvent, websocketUrl } from "../api";
import { demoEvents } from "../demoData";
import { getLatestEventId, uniqueEvents } from "../eventSelectors";
import type { ArcEvent } from "../types";

export type StreamState = "idle" | "loading" | "connected" | "disconnected" | "demo" | "error";

export interface RunStreamResult {
  events: ArcEvent[];
  state: StreamState;
  error?: string;
  latestEventId?: number;
  isDemo: boolean;
}

export function useRunStream(runId?: string, episodeId?: string): RunStreamResult {
  const [events, setEvents] = useState<ArcEvent[]>([]);
  const [state, setState] = useState<StreamState>("idle");
  const [error, setError] = useState<string | undefined>();
  const [isDemo, setIsDemo] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadHistory() {
      if (!episodeId) {
        setEvents([]);
        setState("idle");
        setError(undefined);
        setIsDemo(false);
        return;
      }

      setState("loading");
      setError(undefined);
      try {
        const history = await api.getEvents(episodeId);
        if (cancelled) return;
        setEvents(uniqueEvents(history));
        setIsDemo(false);
        setState("disconnected");
      } catch (err) {
        if (cancelled) return;
        setEvents(uniqueEvents(demoEvents.filter((event) => event.episode_id === episodeId || episodeId === "demo-episode-g03")));
        setError(err instanceof Error ? err.message : "Unable to load episode events");
        setIsDemo(true);
        setState("demo");
      }
    }

    void loadHistory();
    return () => {
      cancelled = true;
    };
  }, [episodeId]);

  useEffect(() => {
    if (!runId || !episodeId || isDemo) return;

    const activeRunId = runId;
    const activeEpisodeId = episodeId;
    let closed = false;
    let reconnectTimer: number | undefined;
    let socket: WebSocket | undefined;

    function connect() {
      socket = new WebSocket(websocketUrl(activeRunId));

      socket.addEventListener("open", () => {
        if (!closed) setState("connected");
      });

      socket.addEventListener("message", (message) => {
        try {
          const event = normalizeEvent(JSON.parse(message.data));
          if (event.episode_id !== activeEpisodeId) return;
          setEvents((current) => uniqueEvents([...current, event]));
        } catch (err) {
          setError(err instanceof Error ? err.message : "Unable to parse stream event");
        }
      });

      socket.addEventListener("error", () => {
        if (!closed) setState("error");
      });

      socket.addEventListener("close", () => {
        if (closed) return;
        setState("disconnected");
        reconnectTimer = window.setTimeout(connect, 2000);
      });
    }

    connect();

    return () => {
      closed = true;
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [episodeId, isDemo, runId]);

  const latestEventId = useMemo(() => getLatestEventId(events), [events]);

  return {
    events,
    state,
    error,
    latestEventId,
    isDemo
  };
}
