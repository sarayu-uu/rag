/**
 * File purpose:
 * - Browser entry point for the React + TypeScript frontend.
 * - Mounts the root App component into #root.
 */

import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);