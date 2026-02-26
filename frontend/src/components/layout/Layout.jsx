import React, { useEffect, useState } from 'react';
import { useLocation, Link, Outlet } from 'react-router-dom';
import { useFilterStore } from '../../store/useFilterStore';
import { useDataStore } from '../../store/useDataStore';
import { useQuery } from '@tanstack/react-query';
import { getCountries, getRegions, getEquipmentTypes, getCustomers, loadData } from '../../api/dataApi';
import api from '../../api/client';
import './Layout.css';

const Layout = () => {
    const location = useLocation();

    // Global filter states
    const {
        country, setCountry,
        region, setRegion,
        equipmentType, setEquipmentType,
        companyName, setCompanyName
    } = useFilterStore();

    // Global Data states
    const { dataLoaded, setDataLoaded, logs, addLog, clearLogs } = useDataStore();

    // UI fetching
    const [loadingDb, setLoadingDb] = useState(false);

    // Queries to fetch the filter lists (Countries, Regions, Equipment)
    const { data: regionsList = ['All'] } = useQuery({ queryKey: ['regions'], queryFn: getRegions, enabled: dataLoaded });
    const { data: countriesList = ['All'] } = useQuery({ queryKey: ['countries'], queryFn: getCountries, enabled: dataLoaded });
    const { data: equipmentList = ['All'] } = useQuery({ queryKey: ['equipments'], queryFn: getEquipmentTypes, enabled: dataLoaded });

    // Dynamic Company Query - dependant on the state of the parent filters
    const { data: filteredCustomersData } = useQuery({
        queryKey: ['filtered_customers', { region, country, equipmentType }],
        queryFn: () => getCustomers({ region, country, equipment_type: equipmentType, company_name: 'All' }),
        enabled: dataLoaded
    });

    const activeCompanies = filteredCustomersData?.customers && filteredCustomersData.customers.length > 0
        ? ['All', ...[...new Set(filteredCustomersData.customers.map(c => c.name))].sort()]
        : ['All'];

    // If an invalid combination occurs, automatically select 'All' for Company Name
    useEffect(() => {
        if (companyName !== 'All' && activeCompanies.length > 1 && !activeCompanies.includes(companyName)) {
            setCompanyName('All');
        }
    }, [activeCompanies, companyName, setCompanyName]);

    // Check Data Loaded status on initial app boot
    useEffect(() => {
        const checkStatus = async () => {
            try {
                const res = await api.get('/data/status');
                setDataLoaded(res.data.loaded);
            } catch (error) {
                console.error("Failed to fetch data status:", error);
            }
        };
        checkStatus();
    }, [setDataLoaded]);

    const handleLoadData = async () => {
        setLoadingDb(true);
        clearLogs();
        try {
            const result = await loadData();
            if (result.success) {
                setDataLoaded(true);
                result.logs.forEach(addLog);
            } else {
                addLog(result.message);
            }
        } catch (error) {
            console.error("Failed to load data:", error);
            addLog("Error loading data: " + error.message);
        } finally {
            setLoadingDb(false);
        }
    }


    const navigation = [
        { name: 'Overview', href: '/' },
        { name: 'Priority Ranking', href: '/ranking' },
        { name: 'Customer Details', href: '/customer' },
    ];

    return (
        <div className="app-container">
            {/* Sidebar */}
            <aside className="sidebar">
                <div className="sidebar-header">
                    <img src="/logo.png" alt="SMS group" className="logo" onError={(e) => e.target.style.display = 'none'} />
                </div>

                <nav className="nav-menu">
                    <h3 className="sidebar-section-title">Navigation</h3>
                    <ul className="nav-list">
                        {navigation.map((item) => (
                            <li key={item.name}>
                                <Link
                                    to={item.href}
                                    className={`nav-link ${location.pathname === item.href ? 'active' : ''}`}
                                >
                                    {item.name}
                                </Link>
                            </li>
                        ))}
                    </ul>
                </nav>

                <div className="sidebar-divider"></div>

                <div className="filter-section">
                    <h3 className="sidebar-section-title">Global Filters</h3>

                    {!dataLoaded ? (
                        <div className="info-box">Load data to enable filters</div>
                    ) : (
                        <div className="filters-form">
                            <div className="form-group">
                                <label>Region</label>
                                <select value={region} onChange={(e) => setRegion(e.target.value)}>
                                    <option value="All">All</option>
                                    {regionsList.map(item => <option key={item} value={item}>{item}</option>)}
                                </select>
                            </div>

                            <div className="form-group">
                                <label>Country</label>
                                <select value={country} onChange={(e) => setCountry(e.target.value)}>
                                    <option value="All">All</option>
                                    {countriesList.map(item => <option key={item} value={item}>{item}</option>)}
                                </select>
                            </div>

                            <div className="form-group">
                                <label>Equipment Type</label>
                                <select value={equipmentType} onChange={(e) => setEquipmentType(e.target.value)}>
                                    <option value="All">All</option>
                                    {equipmentList.map(item => <option key={item} value={item}>{item}</option>)}
                                </select>
                            </div>

                            <div className="form-group">
                                <label>Company Name</label>
                                <select value={companyName} onChange={(e) => setCompanyName(e.target.value)} title="Deep dive into a specific customer">
                                    {activeCompanies.map(item => <option key={item} value={item}>{item}</option>)}
                                </select>
                            </div>
                        </div>
                    )}
                </div>

                <div className="sidebar-divider"></div>

                <div className="settings-section">
                    <h3 className="sidebar-section-title">Settings</h3>
                    <div className="data-management">
                        <h4>Data Management</h4>
                        {dataLoaded && <div className="success-box">Data is loaded</div>}
                        <button
                            className="btn-primary load-btn"
                            onClick={handleLoadData}
                            disabled={loadingDb}
                        >
                            {loadingDb ? 'Loading...' : 'Load Data'}
                        </button>
                    </div>

                    {logs.length > 0 && (
                        <div className="logs-container">
                            <h4>System Logs</h4>
                            <div className="logs-console">
                                {logs.map((log, index) => (
                                    <div key={index} className="log-line">{log}</div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </aside>

            {/* Main Content Area */}
            <main className="main-content">
                <header className="main-header">
                    <h1 className="app-title">AI Supported Sales Application</h1>
                    <p className="app-subtitle">Intelligent Customer Insights and Sales Predictions</p>
                </header>

                <div className="page-content">
                    {/* The specific page content will be injected here by React Router */}
                    <Outlet />
                </div>
            </main>
        </div>
    );
};

export default Layout;
