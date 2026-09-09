import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Home } from "./pages/Home";
import { Game } from "./pages/Game";
import { ChallengeLanding } from "./pages/ChallengeLanding";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/gioca/:token" element={<Game />} />
        <Route path="/sfida/:token" element={<ChallengeLanding />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
