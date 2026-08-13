import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./ConsoleRoot";
import "./figma.css";
import "./login-stitch.css";
import "./ui-motion.css";

const client = new QueryClient();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={client}><App /></QueryClientProvider>
  </React.StrictMode>
);