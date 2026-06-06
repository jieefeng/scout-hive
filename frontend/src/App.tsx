import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import TaskDetail from './pages/TaskDetail';
import ParsePreview from './pages/ParsePreview';

export default function App() {
  return (
    <BrowserRouter>
      <nav style={{ padding: '1rem', borderBottom: '1px solid #eee' }}>
        <Link to="/">Dashboard</Link>
      </nav>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/task/:taskId" element={<TaskDetail />} />
        <Route path="/parse" element={<ParsePreview />} />
      </Routes>
    </BrowserRouter>
  );
}
