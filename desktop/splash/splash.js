"use strict";

const spokes = document.querySelector(".spinner g");
for (let i = 0; i < 12; i++) {
  const r = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  Object.entries({ x: 11, y: 1.5, width: 2, height: 6, rx: 1, transform: `rotate(${i * 30} 12 12)` }).forEach(([k, v]) => r.setAttribute(k, v));
  r.style.animationDelay = `${(i - 12) / 12}s`;
  spokes.appendChild(r);
}

const tauri = window.__TAURI__;
const invoke = (cmd) => (tauri ? tauri.core.invoke(cmd) : Promise.reject(new Error("Not running in the desktop app")));

function render(status) {
  if (!status) return;
  document.getElementById("message").textContent = status.message;
  document.body.classList.toggle("failed", status.state === "failed");
  if (status.state === "failed") document.getElementById("error").textContent = status.message;
  if (status.version) document.getElementById("version").textContent = `Version ${status.version}`;
}

document.getElementById("quit").addEventListener("click", () => invoke("quit"));
document.getElementById("logs").addEventListener("click", () => invoke("open_logs"));
document.getElementById("retry").addEventListener("click", () => {
  render({ state: "starting", message: "Starting the discovery engine…" });
  invoke("retry");
});

if (tauri) {
  tauri.event.listen("engine-status", (event) => render(event.payload));
  invoke("engine_status").then(render);
}
