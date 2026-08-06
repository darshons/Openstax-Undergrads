import { Routes, Route } from 'react-router-dom';
import HomePage from './pages/HomePage';
import Studio from './Studio';
import PlayerPage from './pages/PlayerPage';
import JoinPage from './pages/JoinPage';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/studio" element={<Studio />} />
      <Route path="/player/:scenarioId" element={<PlayerPage />} />
      <Route path="/player" element={<JoinPage />} />
    </Routes>
  );
}
