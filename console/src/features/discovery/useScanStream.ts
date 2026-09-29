import { play } from "@/lib/sound";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useReducer } from "react";
import { invalidateDiscovery, keys } from "@/lib/queries";
import type { ArtefactKind, CoverageLeaf, QuantumStatus, ScanDetail, ScanStage, ScanStatus } from "@/lib/types";

export interface Discovered {
  id: string;
  kind: ArtefactKind;
  name: string;
  quantum: QuantumStatus | null;
  path: string;
  line: number | null;
  /** New to the system (never seen by an earlier scan). */
  new: boolean;
  at: number;
}

interface Sample {
  t: number;
  files: number;
  evidence: number;
}

export interface ScanStream {
  scan: ScanDetail | null;
  coverage: Record<string, CoverageLeaf>;
  feed: Discovered[];
  current: string | null;
  samples: Sample[];
  connection: "connecting" | "live" | "closed" | "error";
}

type Action =
  | { type: "snapshot"; scan: ScanDetail }
  | { type: "stage"; stage: ScanStage; detail: string | null }
  | { type: "tree"; coverage: Record<string, CoverageLeaf> }
  | { type: "progress"; files_total: number; files_done: number; bytes_done?: number; current?: string; evidence: number; artefacts: number; coverage?: Record<string, CoverageLeaf> }
  | { type: "discovered"; artefacts: Omit<Discovered, "at">[]; total_new: number }
  | { type: "finished"; status: ScanStatus; error: string | null; artefacts: number; new_artefacts: number; evidence: number }
  | { type: "connection"; state: ScanStream["connection"] }
  | { type: "reset" };

const FEED_LIMIT = 80;
const SAMPLE_WINDOW_MS = 60_000;

const initial: ScanStream = { scan: null, coverage: {}, feed: [], current: null, samples: [], connection: "connecting" };

function reduce(state: ScanStream, action: Action): ScanStream {
  switch (action.type) {
    case "reset":
      return initial;
    case "connection":
      return { ...state, connection: action.state };
    case "snapshot":
      return { ...state, scan: action.scan, coverage: { ...action.scan.coverage }, connection: "live" };
    case "stage":
      return state.scan ? { ...state, scan: { ...state.scan, status: "running", stage: action.stage, stage_detail: action.detail ?? state.scan.stage_detail } } : state;
    case "tree":
      return { ...state, coverage: { ...action.coverage } };
    case "progress": {
      if (!state.scan) return state;
      // Leaves arrive as absolute values for the directories that changed.
      const coverage = { ...state.coverage, ...action.coverage };
      const now = performance.now();
      const samples = [...state.samples.filter((s) => now - s.t < SAMPLE_WINDOW_MS), { t: now, files: action.files_done, evidence: action.evidence }];
      return {
        ...state,
        coverage,
        samples,
        current: action.current ?? state.current,
        scan: {
          ...state.scan,
          status: "running",
          files_total: action.files_total,
          files_done: action.files_done,
          bytes_done: action.bytes_done ?? state.scan.bytes_done,
          evidence: action.evidence,
          new_artefacts: action.artefacts,
        },
      };
    }
    case "discovered": {
      const at = performance.now();
      const fresh = action.artefacts.map((a) => ({ ...a, at }));
      return { ...state, feed: [...fresh.reverse(), ...state.feed].slice(0, FEED_LIMIT) };
    }
    case "finished":
      return state.scan
        ? {
            ...state,
            current: null,
            connection: "closed",
            scan: {
              ...state.scan,
              status: action.status,
              error: action.error,
              artefacts: action.artefacts,
              new_artefacts: action.new_artefacts,
              evidence: action.evidence,
              stage: action.status === "succeeded" ? "done" : state.scan.stage,
            },
          }
        : state;
  }
}

const EVENTS = ["snapshot", "stage", "tree", "progress", "discovered", "finished"] as const;

/**
 * Follows one scan over Server-Sent Events: a snapshot first, then stage,
 * coverage, progress and discovery events until it finishes. The stream is
 * closed explicitly once the scan is over (EventSource would otherwise
 * reconnect forever), and the inventory queries refresh when it ends.
 */
export function useScanStream(scanId: string): ScanStream {
  const [state, dispatch] = useReducer(reduce, initial);
  const client = useQueryClient();

  useEffect(() => {
    dispatch({ type: "reset" });
    const source = new EventSource(`/api/v1/scans/${encodeURIComponent(scanId)}/events`, { withCredentials: true });
    let done = false;

    const finish = () => {
      done = true;
      source.close();
      dispatch({ type: "connection", state: "closed" });
      void client.invalidateQueries({ queryKey: keys.scan(scanId) });
      void invalidateDiscovery(client);
    };

    const handlers = EVENTS.map((name) => {
      const handler = (event: MessageEvent<string>) => {
        const data = JSON.parse(event.data);
        if (name === "snapshot") {
          dispatch({ type: "snapshot", scan: data as ScanDetail });
          if (data.status !== "queued" && data.status !== "running") finish();
        } else {
          dispatch({ ...data, type: name } as Action);
          if (name === "finished") {
            // Heard live, not on reload: a chime as the scan completes.
            if (data.status === "succeeded") play("notify");
            else if (data.status === "failed") play("error");
            finish();
          }
        }
      };
      source.addEventListener(name, handler as EventListener);
      return [name, handler] as const;
    });

    source.onerror = () => {
      if (done) return;
      // EventSource retries on its own; surface the gap without tearing down.
      dispatch({ type: "connection", state: source.readyState === EventSource.CLOSED ? "error" : "connecting" });
    };

    return () => {
      done = true;
      handlers.forEach(([name, handler]) => source.removeEventListener(name, handler as EventListener));
      source.close();
    };
  }, [scanId, client]);

  return state;
}

/** Files per second over the last few seconds of samples. */
export function throughput(samples: Sample[], windowMs = 4000): number {
  if (samples.length < 2) return 0;
  const last = samples[samples.length - 1];
  const first = samples.find((s) => last.t - s.t <= windowMs) ?? samples[0];
  const dt = (last.t - first.t) / 1000;
  return dt > 0.2 ? (last.files - first.files) / dt : 0;
}
