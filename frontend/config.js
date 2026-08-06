// ---------------------------------------------------------------------------
// Sada — backend connection config.
//
// This project has no build step (plain HTML/CSS/JS), so there's no bundler
// to inject a real environment variable at build time. This file is the
// equivalent: ONE place to set the backend URL, loaded before app.js.
//
// Leave it empty ("") for same-origin deployments (GitHub Codespaces, or any
// setup where the frontend is served by the same FastAPI app as the API).
//
// For split hosting (GitHub Pages frontend + Kaggle backend), Cloudflare
// Tunnel hands out a new random https://xxxx.trycloudflare.com URL every time
// the Kaggle notebook's Quick Tunnel is (re)started — so there's no single
// fixed value that stays correct across sessions. In that case, either:
//   1. Leave API_BASE_URL empty and paste the tunnel URL at runtime into the
//      "رابط الخادم" (server URL) button in the UI — it's saved to the
//      browser's localStorage and takes priority over the value below
//      (see getApiBase() in app.js). This is the recommended flow for
//      Cloudflare Quick Tunnels.
//   2. Set API_BASE_URL below if you're running a named Cloudflare Tunnel
//      with a stable hostname (or any other fixed backend URL), so every
//      visitor gets it by default with no manual step.
// ---------------------------------------------------------------------------
const API_BASE_URL = "";
