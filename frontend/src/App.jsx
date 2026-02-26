import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/layout/Layout';
import DashboardPage from './pages/DashboardPage';

// Placeholder Pages (To be built in later Modules)
const Ranking = () => <div><h2>Priority Ranking Placeholder</h2><p>ML priorities will go here.</p></div>;
const Customer = () => <div><h2>Customer Details Placeholder</h2><p>Generated Steckbriefs will go here.</p></div>;

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="ranking" element={<Ranking />} />
          <Route path="customer" element={<Customer />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;
