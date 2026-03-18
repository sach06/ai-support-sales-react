import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/layout/Layout';

const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const RankingPage = lazy(() => import('./pages/RankingPage'));
const CustomerDetailPage = lazy(() => import('./pages/CustomerDetailPage'));

const PageLoader = () => <div className="loading-spinner">Loading page...</div>;

function App() {
  return (
    <Router>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<DashboardPage />} />
            <Route path="ranking" element={<RankingPage />} />
            <Route path="customer" element={<CustomerDetailPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </Suspense>
    </Router>
  );
}

export default App;
