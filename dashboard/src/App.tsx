import { HashRouter, Routes, Route } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import CategoryView from "./pages/CategoryView";
import BrandView from "./pages/BrandView";

// HashRouter, not BrowserRouter: on GitHub Pages a real-path deep link / refresh would 404.
export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/category/:name" element={<CategoryView />} />
        <Route path="/brand/:name" element={<BrandView />} />
      </Routes>
    </HashRouter>
  );
}
