/**
 * Interface sounds, in the manner of macOS and iOS: quiet, short, and only
 * where they confirm something. Every sound is synthesised with Web Audio (no
 * audio files), so each is a few oscillators and an envelope, and the
 * AudioContext is created only after the first user gesture, as browsers
 * require. Preferences are per device.
 */
import { useSyncExternalStore } from "react";

export type SoundName = "tap" | "toggleOn" | "toggleOff" | "success" | "error" | "notify" | "open" | "close";

interface SoundPrefs {
  enabled: boolean;
  volume: number; // 0..1
}

const KEY = "falcon.sound";
const listeners = new Set<() => void>();

function read(): SoundPrefs {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? "null");
    if (raw && typeof raw.enabled === "boolean" && typeof raw.volume === "number") return { enabled: raw.enabled, volume: Math.min(1, Math.max(0, raw.volume)) };
  } catch {
    /* storage unavailable or malformed: defaults */
  }
  return { enabled: true, volume: 0.55 };
}

let prefs = read();

export function setSoundPrefs(next: Partial<SoundPrefs>): void {
  prefs = { ...prefs, ...next };
  try {
    localStorage.setItem(KEY, JSON.stringify(prefs));
  } catch {
    /* the choice lasts for this page view */
  }
  listeners.forEach((l) => l());
}

export function useSoundPrefs(): SoundPrefs {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => prefs,
  );
}

let ctx: AudioContext | null = null;
let master: GainNode | null = null;

function audio(): AudioContext | null {
  if (typeof window === "undefined") return null;
  const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  if (!ctx) {
    try {
      ctx = new Ctor({ latencyHint: "interactive" });
      master = ctx.createGain();
      // A gentle high shelf cut keeps every sound soft rather than clicky.
      const tone = ctx.createBiquadFilter();
      tone.type = "lowpass";
      tone.frequency.value = 6500;
      master.connect(tone).connect(ctx.destination);
    } catch {
      return null;
    }
  }
  if (ctx.state === "suspended") void ctx.resume();
  return ctx;
}

/** A single voice: an oscillator whose pitch glides, under a fast attack and exponential decay. */
function voice(ac: AudioContext, at: number, { type = "sine", from, to = from, attack = 0.002, decay, gain }: {
  type?: OscillatorType; from: number; to?: number; attack?: number; decay: number; gain: number;
}) {
  const osc = ac.createOscillator();
  const env = ac.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(from, at);
  if (to !== from) osc.frequency.exponentialRampToValueAtTime(to, at + decay * 0.6);
  env.gain.setValueAtTime(0.0001, at);
  env.gain.exponentialRampToValueAtTime(gain, at + attack);
  env.gain.exponentialRampToValueAtTime(0.0001, at + attack + decay);
  osc.connect(env).connect(master!);
  osc.start(at);
  osc.stop(at + attack + decay + 0.02);
}

const RECIPES: Record<SoundName, (ac: AudioContext, t: number) => void> = {
  // A soft, woody tick, like a trackpad click heard through headphones.
  tap: (ac, t) => {
    voice(ac, t, { type: "triangle", from: 1150, to: 620, decay: 0.035, gain: 0.16 });
    voice(ac, t, { type: "sine", from: 2600, to: 2200, decay: 0.012, gain: 0.05 });
  },
  toggleOn: (ac, t) => {
    voice(ac, t, { type: "triangle", from: 760, decay: 0.03, gain: 0.13 });
    voice(ac, t + 0.045, { type: "triangle", from: 1140, decay: 0.04, gain: 0.13 });
  },
  toggleOff: (ac, t) => {
    voice(ac, t, { type: "triangle", from: 1140, decay: 0.03, gain: 0.12 });
    voice(ac, t + 0.045, { type: "triangle", from: 760, decay: 0.04, gain: 0.12 });
  },
  // Two bell partials a fifth apart: the "done" of a completed task.
  success: (ac, t) => {
    voice(ac, t, { from: 1318.5, decay: 0.42, gain: 0.11 });
    voice(ac, t, { from: 2637, decay: 0.2, gain: 0.03 });
    voice(ac, t + 0.09, { from: 1975.5, decay: 0.55, gain: 0.1 });
    voice(ac, t + 0.09, { from: 3951, decay: 0.22, gain: 0.025 });
  },
  error: (ac, t) => {
    voice(ac, t, { type: "triangle", from: 392, to: 370, decay: 0.12, gain: 0.16 });
    voice(ac, t + 0.14, { type: "triangle", from: 311, to: 294, decay: 0.2, gain: 0.16 });
  },
  // Three rising notes: something finished in the background (a scan).
  notify: (ac, t) => {
    [1046.5, 1318.5, 1568].forEach((f, i) => voice(ac, t + i * 0.085, { from: f, decay: 0.35 - i * 0.05, gain: 0.09 }));
  },
  open: (ac, t) => voice(ac, t, { type: "sine", from: 520, to: 880, decay: 0.09, gain: 0.07 }),
  close: (ac, t) => voice(ac, t, { type: "sine", from: 880, to: 520, decay: 0.08, gain: 0.06 }),
};

let last = 0;

export function play(name: SoundName, { force = false }: { force?: boolean } = {}): void {
  if ((!prefs.enabled && !force) || (typeof document !== "undefined" && document.hidden)) return;
  const now = performance.now();
  // Taps are rate-limited so a double click or a drag never becomes a buzz.
  if (name === "tap" && now - last < 45) return;
  last = now;
  const ac = audio();
  if (!ac || !master) return;
  master.gain.setValueAtTime(Math.max(0.0001, prefs.volume), ac.currentTime);
  RECIPES[name](ac, ac.currentTime + 0.005);
}
