import { Routes, Route } from "react-router-dom";
import Home from "./pages/Home";
import Download from "./pages/Download";
import ConstructorForm from "./components/ConstructorForm";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/constructor" element={<ConstructorForm />} />
      <Route path="/download" element={<Download />} />
    </Routes>
  );
}
