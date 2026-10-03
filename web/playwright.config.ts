// UI smoke test (spec §10.3, M3 gate). Starts its own API (dev sign-in, fresh
// SQLite file) and web dev server. Run with the project's Python venv active:
//   . ../.venv/bin/activate && npm run e2e
import { defineConfig } from "@playwright/test";

const API = 8001, WEB = 5174;
export default defineConfig({
  testDir: "e2e",
  timeout: 120_000,
  use: { baseURL: `http://localhost:${WEB}`, viewport: { width: 1440, height: 1000 } },
  webServer: [
    {
      command:
        `cd ../api && python -c "from app.db import migrate; migrate('sqlite:///./e2e.db', fresh=True)" && ` +
        `ENV=development AUTH_MODE=dev DATABASE_URL=sqlite:///./e2e.db CORS_ORIGINS=http://localhost:${WEB} ` +
        `python -m uvicorn app.main:app --port ${API}`,
      url: `http://localhost:${API}/v1/projects`,
      reuseExistingServer: false,
    },
    {
      command: `VITE_AUTH_MODE=dev VITE_API_URL=http://localhost:${API} npx vite --port ${WEB} --strictPort`,
      url: `http://localhost:${WEB}`,
      reuseExistingServer: false,
    },
  ],
});
