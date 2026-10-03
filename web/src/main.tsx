import "@xyflow/react/dist/style.css";
import "./styles.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App.tsx";
import { AuthGate } from "./auth.tsx";
import { symbolDefs, tokensCss } from "./design/css.ts";

// Design tokens -> CSS variables; symbols -> one hidden SVG sprite (spec §8.4).
const style = document.createElement("style");
style.textContent = tokensCss();
document.head.prepend(style);
document.body.insertAdjacentHTML(
  "afterbegin",
  `<svg width="0" height="0" class="sprite" aria-hidden="true">${symbolDefs()}</svg>`,
);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthGate>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </AuthGate>
  </StrictMode>,
);
