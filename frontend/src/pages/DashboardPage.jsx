import React, { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useFilterStore } from '../store/useFilterStore';
import { useDataStore } from '../store/useDataStore';
import api from '../api/client';
import MetricCard from './MetricCard';
import GeoMap from './GeoMap';
import InventoryTable from './InventoryTable';
import MatchQualityPanel from './MatchQualityPanel';
import StatisticsPanel from './StatisticsPanel';
import NewsPanel from './NewsPanel';
import './Dashboard.css';

const fetchDashboardData = async ({ queryKey }) => {
    const [_key, filters] = queryKey;
    const response = await api.get('/data/plants', {
        params: {
            country: filters.country,
            region: filters.region,
            equipment_type: filters.equipmentType,
            company_name: filters.companyName,
        },
    });
    return response.data;
};

const fetchStats = async ({ queryKey }) => {
    const [_key, filters] = queryKey;
    const response = await api.get('/data/stats', {
        params: {
            country: filters.country,
            region: filters.region,
            equipment_type: filters.equipmentType,
            company_name: filters.companyName,
        },
    });
    return response.data;
};

const fetchCustomers = async ({ queryKey }) => {
    const [_key, filters] = queryKey;
    const response = await api.get('/data/customers', {
        params: {
            country: filters.country,
            region: filters.region,
            equipment_type: filters.equipmentType,
            company_name: filters.companyName,
        },
    });
    return response.data;
};

const DashboardPage = () => {
    const { country, region, equipmentType, companyName } = useFilterStore();
    const { dataLoaded } = useDataStore();

    const filters = { country, region, equipmentType, companyName };

    const { data: dashboardData, isLoading, isError } = useQuery({
        queryKey: ['dashboard_plants', filters],
        queryFn: fetchDashboardData,
        enabled: dataLoaded,
    });

    const { data: statsData } = useQuery({
        queryKey: ['dashboard_stats', filters],
        queryFn: fetchStats,
        enabled: dataLoaded,
        staleTime: 60_000,
    });

    const { data: customerData } = useQuery({
        queryKey: ['dashboard_customers', filters],
        queryFn: fetchCustomers,
        enabled: dataLoaded,
        staleTime: 60_000,
    });

    const plants = dashboardData?.plants || [];
    const customers = customerData?.customers || [];

    const customerMetrics = useMemo(() => {
        const total = customers.length;
        if (total === 0) {
            return {
                total: 0,
                matchedCrmBcg: 0,
                crmOnly: 0,
                bcgOnly: 0,
            };
        }

        const matchedCrmBcg = customers.filter(
            (row) => Boolean(row.crm_name) && Boolean(row.bcg_name)
        ).length;
        const crmOnly = customers.filter(
            (row) => Boolean(row.crm_name) && !row.bcg_name
        ).length;
        const bcgOnly = customers.filter(
            (row) => Boolean(row.bcg_name) && !row.crm_name
        ).length;

        return {
            total,
            matchedCrmBcg,
            crmOnly,
            bcgOnly,
        };
    }, [customers]);

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
                <MetricCard title="Total Customers" value={customerMetrics.total} subtitle="In Current Selection" />
                <MetricCard title="CRM ↔ BCG Matched" value={customerMetrics.matchedCrmBcg}
                    subtitle={customerMetrics.total > 0 ? `${Math.round((customerMetrics.matchedCrmBcg / customerMetrics.total) * 100)}% of total` : '0%'}
                    colorClass="metric-excellent" />
                <MetricCard title="CRM-Only Customers" value={customerMetrics.crmOnly}
                    subtitle={customerMetrics.total > 0 ? `${Math.round((customerMetrics.crmOnly / customerMetrics.total) * 100)}% of total` : '0%'}
                    colorClass="metric-good" />
                <MetricCard title="BCG-Only Customers" value={customerMetrics.bcgOnly}
                    subtitle={customerMetrics.total > 0 ? `${Math.round((customerMetrics.bcgOnly / customerMetrics.total) * 100)}% of total` : '0%'}
                    colorClass="metric-poor" />
            </div>

            {/* Map + Statistics Panel Row */}
            <div className="dashboard-main-row">
                <div className="map-panel">
                    <h3>Geographic Distribution</h3>
                    <div className="map-container">
                        <GeoMap data={plants} />
                    </div>
                </div>

                <div className="stats-section match-panel">
                    <h3>Fleet Statistics &amp; Distributions</h3>
                    <StatisticsPanel summary={statsData?.summary} displayTotal={plants.length} />
                </div>
            </div>

            {/* Bottom Row: Inventory and News */}
            <div className="dashboard-bottom-row">
                <div className="inventory-panel">
                    <h3>Plant Inventory</h3>
                    <InventoryTable data={plants} />
                </div>
                <div className="news-panel-wrapper">
                    <h3>{companyName === 'All' ? 'Global Market News' : `Latest '${companyName}' News`}</h3>
                    <NewsPanel companyName={companyName} equipmentType={equipmentType} country={country} />
                </div>
            </div>
        </div>
    );
};

export default DashboardPage;
