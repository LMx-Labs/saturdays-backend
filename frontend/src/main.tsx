import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import ProductApp from "./ProductApp";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ProductApp />
  </StrictMode>,
);
