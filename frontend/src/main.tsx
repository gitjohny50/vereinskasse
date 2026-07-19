import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./styles.css";

// Gespeichertes Farbschema vor dem ersten Render setzen (kein Aufblitzen).
document.documentElement.dataset.theme = localStorage.getItem("vk_theme") || "indigo";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
