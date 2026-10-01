import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";

import { App } from "./app/App.jsx";
import "./styles/global.css";

createRoot(document.getElementById("root")).render(
  <BrowserRouter>
    <App />
  </BrowserRouter>,
);
