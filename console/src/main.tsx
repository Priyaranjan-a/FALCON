import "@fontsource-variable/inter/opsz.css";
import "@fontsource-variable/jetbrains-mono/wght.css";
import "./design/index.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./app/App";
import { installPointerLight } from "./design/pointer";

installPointerLight();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
