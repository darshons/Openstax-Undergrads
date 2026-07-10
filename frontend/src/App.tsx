import { Routes, Route } from 'react-router-dom';
import Studio from './Studio';
import PlayerPage from './pages/PlayerPage';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Studio />} />
      <Route path="/player/:scenarioId" element={<PlayerPage />} />
    </Routes>
  );
}
