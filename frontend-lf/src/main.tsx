import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'
import { JazzReactProvider } from "jazz-tools/react";
import { JazzInspector } from "jazz-tools/inspector";
import { AuthProvider } from "jazz-tools/better-auth/auth/react";
import { betterAuthClient } from "./lib/authClient";
import { MyAppAccount } from "./schema";

export const APPLICATION_NAME = "Veridash Jazz";

createRoot(document.getElementById('root')!).render(
  <JazzReactProvider sync={{ peer: "ws://localhost:4200/" }} AccountSchema={MyAppAccount}>
    <AuthProvider betterAuthClient={betterAuthClient}>
      <StrictMode>
        <App />
        <JazzInspector />
      </StrictMode>
    </AuthProvider>
  </JazzReactProvider>,
);

