
  import { createRoot } from "react-dom/client";
  import App from "./app/App.tsx";
  import { reportClientError } from "./app/api";
  import "./styles/index.css";

  // Errors outside rendering (event handlers, promises nobody awaited)
  // would otherwise only reach the visitor's console.
  window.addEventListener("error", e => reportClientError(e.error ?? e.message));
  window.addEventListener("unhandledrejection", e => reportClientError(e.reason));

  createRoot(document.getElementById("root")!).render(<App />);
  