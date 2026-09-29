/**
 * Feeds the pointer position to `.hover-light` surfaces as --hx/--hy, once per
 * frame, from a single passive listener for the whole app.
 */
export function installPointerLight(): () => void {
  let frame = 0;
  let target: HTMLElement | null = null;
  let x = 0;
  let y = 0;

  const paint = () => {
    frame = 0;
    if (!target) return;
    const box = target.getBoundingClientRect();
    target.style.setProperty("--hx", `${x - box.left}px`);
    target.style.setProperty("--hy", `${y - box.top}px`);
  };

  const onMove = (event: PointerEvent) => {
    if (event.pointerType !== "mouse" && event.pointerType !== "pen") return;
    target = (event.target as Element | null)?.closest?.<HTMLElement>(".hover-light") ?? null;
    if (!target) return;
    x = event.clientX;
    y = event.clientY;
    if (!frame) frame = requestAnimationFrame(paint);
  };

  document.addEventListener("pointermove", onMove, { passive: true });
  return () => {
    document.removeEventListener("pointermove", onMove);
    if (frame) cancelAnimationFrame(frame);
  };
}
