import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { AppProvider } from "./context/AppContext";
import { I18nProvider } from "./context/I18nContext";

// Global reset styles
const globalStyles = document.createElement("style");
globalStyles.textContent = `
  *, *::before, *::after {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }
  html, body, #root {
    height: 100%;
    width: 100%;
    overflow: hidden;
  }
  body {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: system-ui, -apple-system, sans-serif;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }
  ::-webkit-scrollbar {
    width: 8px;
    height: 8px;
  }
  ::-webkit-scrollbar-track {
    background: #181825;
  }
  ::-webkit-scrollbar-thumb {
    background: #313244;
    border-radius: 4px;
  }
  ::-webkit-scrollbar-thumb:hover {
    background: #45475a;
  }
  @keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
  }
`;
document.head.appendChild(globalStyles);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <I18nProvider>
      <AppProvider>
        <App />
      </AppProvider>
    </I18nProvider>
  </React.StrictMode>
);
