import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'
import { JazzReactProvider } from "jazz-tools/react";
import { JazzInspector } from "jazz-tools/inspector";
import { MyAppAccount } from "./schema";

export const APPLICATION_NAME = "Veridash Jazz";

createRoot(document.getElementById('root')!).render(
  <JazzReactProvider sync={{ peer: "ws://localhost:4200/" }} AccountSchema={MyAppAccount}>
    <StrictMode>
      <App />
      <JazzInspector />
    </StrictMode>
  </JazzReactProvider>,
);

