import React, { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useFilterStore } from '../../../store/useFilterStore';
import { useDataStore } from '../../../store/useDataStore';
import api from '../../../api/client';
import MetricCard from './MetricCard';
import GeoMap from './GeoMap';
import InventoryTable from './InventoryTable';
import MatchQualityPanel from './MatchQualityPanel';
import NewsPanel from './NewsPanel';
import './Dashboard.css';

const fetchDashboardData = async ({ queryKey }) => {
    const [_key, filters] = queryKey;
    // We need plant data for the map and inventory table
    const response = await api.get('/data/plants', {
        params: {
            country: filters.country,
            region: filters.region,
            equipment_type: filters.equipmentType,
            company_name: filters.companyName
        }
    });
    return response.data;
};

const DashboardPage = () => {
    const { country, region, equipmentType, companyName } = useFilterStore();
    const { dataLoaded } = useDataStore();

    // Query for dashboard plant data
    const { data: dashboardData, isLoading, isError } = useQuery({
        queryKey: ['dashboard_plants', { country, region, equipmentType, companyName }],
        queryFn: fetchDashboardData,
        enabled: dataLoaded,
    });

    const plants = dashboardData?.plants || [];

    // Calculate match metrics
    const metrics = useMemo(() => {
        let total = plants.length;
        if (total === 0) return { total: 0, excellent: 0, good: 0, okay: 0, poor: 0 };

        const counts = plants.reduce((acc, plant) => {
            const type = plant.match_type || 'Poor';
            acc[type] = (acc[type] || 0) + 1;
            return acc;
        }, {});

        return {
            total,
            excellent: counts['Excellent'] || 0,
            good: counts['Good'] || 0,
            okay: counts['Okay'] || 0,
            poor: counts['Poor'] || 0
        };
    }, [plants]);

    if (!dataLoaded) {
        return (
            <div className="dashboard-empty-state">
                <h2>Welcome to AI Supported Sales App</h2>
                <p>Please load data from the side menu to view the dashboard.</p>
            </div>
        );
    }

    if (isLoading) return <div className="loading-spinner">Loading dashboard data...</div>;
    if (isError) return <div className="error-message">Error loading dashboard data.</div>;

    return (
        <div className="dashboard-container">
            {/* Top Metrics Row */}
            <div className="metrics-row">
                <MetricCard
                    title="Total Machines"
                    value={metrics.total}
                    subtitle="In Selection"
                />
                <MetricCard
                    title="Excellent Matches"
                    value={metrics.excellent}
                    subtitle={metrics.total > 0 ? `${Math.round((metrics.excellent / metrics.total) * 100)}% of total` : '0%'}
                    colorClass="metric-excellent"
                />
                <MetricCard
                    title="Good Matches"
                    value={metrics.good}
                    subtitle={metrics.total > 0 ? `${Math.round((metrics.good / metrics.total) * 100)}% of total` : '0%'}
                    colorClass="metric-good"
                />
                <MetricCard
                    title="Okay Matches"
                    value={metrics.okay}
                    subtitle={metrics.total > 0 ? `${Math.round((metrics.okay / metrics.total) * 100)}% of total` : '0%'}
                    colorClass="metric-okay"
                />
                <MetricCard
                    title="Poor Matches"
                    value={metrics.poor}
                    subtitle={metrics.total > 0 ? `${Math.round((metrics.poor / metrics.total) * 100)}% of total` : '0%'}
                    colorClass="metric-poor"
                />
            </div>

            {/* Map and Match Details Row */}
            <div className="dashboard-main-row">
                <div className="map-panel">
                    <h3>Geographic Distribution</h3>
                    <div className="map-container">
                        <GeoMap data={plants} />
                    </div>
                </div>

                <div className="match-panel">
                    <h3>Data Linkage Quality</h3>
                    <MatchQualityPanel data={plants} />
                </div>
            </div>

            {/* Bottom Row: Inventory and News */}
            <div className="dashboard-bottom-row">
                <div className="inventory-panel">
                    <h3>Plant Inventory</h3>
                    <InventoryTable data={plants} />
                </div>

                {companyName !== 'All' && (
                    <div className="news-panel-wrapper">
                        <h3>Latest '{companyName}' News</h3>
                        <NewsPanel companyName={companyName} />
                    </div>
                )}
            </div>
        </div>
    );
};

export default DashboardPage;
