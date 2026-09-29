import { useEffect, useRef, type CSSProperties } from "react";
import { cn } from "../cn";

/**
 * A small peregrine falcon in side view, facing right. Its wings pivot at the
 * shoulder: `flap` beats them, `glide` holds them spread. Colour follows the
 * accent, so it matches whatever accent the user chose.
 */
export function FalconBird({ size = 44, className, style }: { size?: number; className?: string; style?: CSSProperties }) {
  return (
    <svg width={size} height={(size * 40) / 64} viewBox="0 0 64 40" className={cn("falcon-bird overflow-visible", className)} style={style} aria-hidden>
      <defs>
        <linearGradient id="falcon-body" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="var(--accent-hover)" />
          <stop offset="1" stopColor="var(--accent-pressed)" />
        </linearGradient>
        <linearGradient id="falcon-wing" x1="1" y1="1" x2="0" y2="0">
          <stop offset="0" stopColor="var(--accent)" />
          <stop offset="1" stopColor="var(--accent-pressed)" />
        </linearGradient>
      </defs>
      {/* far wing, behind the body */}
      <g className="falcon-wing falcon-wing-far">
        <path d="M35 18.2 C 30 12.5 24.5 8 13 4.2 C 19 8.8 23.5 12.8 26.5 16.8 C 28.5 18.7 31 19.3 35 18.2 Z" fill="url(#falcon-wing)" opacity="0.5" />
      </g>
      {/* tail */}
      <path d="M14.5 20.4 L3 16.4 L5.2 20.9 L3.4 25.6 Z" fill="var(--accent-pressed)" />
      {/* body and head */}
      <path d="M12.5 21 C 18 16.6 33.5 14.6 43.5 15.9 C 48.8 16.6 52.6 18.3 53.3 20 C 50.7 22.6 44 24.6 34 24.9 C 24 25.1 17.3 23.6 12.5 21 Z" fill="url(#falcon-body)" />
      <circle cx="50" cy="18.3" r="4.7" fill="url(#falcon-body)" />
      {/* pale throat and belly */}
      <path d="M45.5 21.4 C 48 21.6 50.5 21.1 52.2 20.1 C 51 22.4 47.6 23.6 43 24 C 44 23 44.8 22.2 45.5 21.4 Z" fill="#fff" opacity="0.55" />
      {/* the peregrine's dark hood, over the crown and down the nape */}
      <path
        d="M44.8 17.6 C 45.6 14.3 49.2 12.8 52.3 13.8 C 54.2 14.5 55.1 15.9 54.9 17.3 C 53.4 16.8 52.2 16.9 51.3 17.9 C 50.8 19.6 50.6 21 49.9 22.3 C 48.7 20.9 47.6 19.4 44.8 17.6 Z"
        style={{ fill: "color-mix(in srgb, var(--accent-pressed) 45%, #0a1426)" }}
      />
      {/* hooked beak with its yellow cere */}
      <path d="M54.3 17.1 C 56.9 17.1 58.7 18.3 58.9 19.9 C 58.9 20.5 58.5 20.9 58 21 C 57.8 20.2 57.1 19.8 56.1 19.9 C 55.4 20 54.9 20.3 54.5 20.6 Z" fill="#2c2c2e" />
      <path d="M54.1 17.2 C 55.2 17 56.1 17.3 56.5 17.8 L 54.5 18.6 Z" fill="#f5b83d" />
      {/* dark eye in a yellow ring */}
      <circle cx="52.1" cy="17.5" r="1.45" fill="#f5c451" />
      <circle cx="52.2" cy="17.5" r="0.95" fill="#16161a" />
      <circle cx="52.55" cy="17.15" r="0.3" fill="#fff" />
      {/* near wing, in front */}
      <g className="falcon-wing falcon-wing-near">
        <path d="M37 18.6 C 31.5 11.8 24.5 6.2 8.5 1.2 C 15.5 6.4 21.5 11.4 25.8 16.2 C 28 18.8 31.5 19.9 37 18.6 Z" fill="url(#falcon-wing)" />
        <path d="M30 14.2 C 25 10.6 19.5 7.4 13.5 4.8 M 27.2 16.4 C 23 13.4 18.5 10.8 13.8 8.8" stroke="#fff" strokeOpacity="0.28" strokeWidth="0.7" strokeLinecap="round" fill="none" />
      </g>
    </svg>
  );
}

export interface Point {
  x: number;
  y: number;
}

interface FlyerProps {
  /** Position at time t (seconds) for a viewport of w × h. */
  path: (t: number, w: number, h: number) => Point;
  /** Where the bird starts before it joins the path (entering from off-screen). */
  enterFrom?: (w: number, h: number) => Point;
  /** When set, the bird leaves the path and flies away, fading out. */
  leaving?: boolean;
  onGone?: () => void;
  size?: number;
  trail?: boolean;
  className?: string;
}

/**
 * Flies a FalconBird along a path with physical heading: it banks into
 * turns, rolls over when it reverses direction, flaps while climbing and
 * glides while descending. One requestAnimationFrame loop writes transforms
 * directly (no React renders per frame), so it costs almost nothing.
 */
export function Flyer({ path, enterFrom, leaving = false, onGone, size = 44, trail = true, className }: FlyerProps) {
  const bird = useRef<HTMLDivElement>(null);
  const wake = useRef<SVGSVGElement>(null);
  const state = useRef({ leaving, onGone });
  state.current = { leaving, onGone };

  useEffect(() => {
    const node = bird.current;
    if (!node) return;
    let frame = 0;
    const start = performance.now();
    let prev: Point | null = null;
    let roll = 1; // +1 upright facing right, -1 mirrored; smoothed through 0 for a barrel roll
    let angle = 0;
    let gliding = false;
    let exitAt = 0;
    let exitFrom: Point = { x: 0, y: 0 };
    let exitVel: Point = { x: 0, y: 0 };
    const history: Point[] = [];
    const dots = wake.current ? Array.from(wake.current.querySelectorAll("circle")) : [];

    const step = (now: number) => {
      const w = window.innerWidth;
      const h = window.innerHeight;
      const t = (now - start) / 1000;
      let p = path(t, w, h);

      // Enter: blend from off-screen onto the path over the first 0.9 s.
      if (enterFrom && t < 0.9) {
        const k = 1 - Math.pow(1 - t / 0.9, 3);
        const from = enterFrom(w, h);
        p = { x: from.x + (p.x - from.x) * k, y: from.y + (p.y - from.y) * k };
      }
      // Leave: keep the current velocity, climb and accelerate away, fade out.
      let opacity = Math.min(1, t / 0.25);
      if (state.current.leaving) {
        if (!exitAt) {
          exitAt = now;
          exitFrom = prev ?? p;
          const v = prev ? { x: p.x - prev.x, y: p.y - prev.y } : { x: 6, y: 0 };
          const speed = Math.max(6, Math.hypot(v.x, v.y));
          exitVel = { x: (v.x / speed) * 7 + (v.x >= 0 ? 3 : -3), y: -4 };
        }
        const s = (now - exitAt) / 1000;
        p = { x: exitFrom.x + exitVel.x * 60 * s * (1 + s * 1.6), y: exitFrom.y + exitVel.y * 60 * s * (1 + s * 1.2) };
        opacity = Math.max(0, 1 - s / 0.75);
        if (s > 0.8) {
          state.current.onGone?.();
          return;
        }
      }

      if (prev) {
        const vx = p.x - prev.x;
        const vy = p.y - prev.y;
        if (Math.hypot(vx, vy) > 0.05) {
          const target = Math.atan2(vy, vx);
          let d = target - angle;
          d = Math.atan2(Math.sin(d), Math.cos(d));
          angle += d * 0.25;
          roll += ((vx >= 0 ? 1 : -1) - roll) * 0.12;
          // Glide on the way down, beat the wings on the way up (with hysteresis).
          const perFrameDown = vy;
          if (!gliding && perFrameDown > 1.6) gliding = true;
          else if (gliding && perFrameDown < 0.4) gliding = false;
        }
      }
      prev = p;
      node.style.opacity = String(opacity);
      node.style.transform = `translate3d(${p.x - size / 2}px, ${p.y - size * 0.31}px, 0) rotate(${angle}rad) scaleY(${Math.abs(roll) < 0.08 ? 0.08 * Math.sign(roll || 1) : roll})`;
      node.classList.toggle("is-gliding", gliding);

      if (dots.length) {
        history.unshift(p);
        if (history.length > dots.length * 3) history.pop();
        dots.forEach((dot, i) => {
          const q = history[i * 3 + 2];
          if (!q) return;
          dot.setAttribute("cx", String(q.x));
          dot.setAttribute("cy", String(q.y));
          dot.setAttribute("opacity", String(opacity * 0.34 * (1 - i / dots.length)));
        });
      }
      frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
    // The path function is read on every frame; restarting on identity changes would jump the bird.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [size]);

  return (
    <div className={cn("pointer-events-none fixed inset-0", className)} aria-hidden>
      {trail && (
        <svg ref={wake} className="absolute inset-0 h-full w-full overflow-visible">
          {Array.from({ length: 10 }, (_, i) => (
            <circle key={i} r={Math.max(0.8, 2.4 - i * 0.18)} fill="var(--accent)" opacity="0" />
          ))}
        </svg>
      )}
      <div ref={bird} className="falcon-flyer absolute left-0 top-0 origin-center will-change-transform" style={{ opacity: 0 }}>
        <FalconBird size={size} />
      </div>
    </div>
  );
}
