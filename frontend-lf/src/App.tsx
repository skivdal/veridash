import './App.css';
import Demo from "./Demo";
import Projects from './Projects';
//@ts-ignore
import { Router } from "./components/Router";
//@ts-ignore
import { Link } from "./components/Link";

function NotFound() {
  return <h1>404 - Not Found</h1>;
}

export default function App() {
  return (
    <Router
      routes={{
        "/": Demo,
        "/projects": Projects,
        "*": NotFound, // fallback
      }}
    />
  );
}

