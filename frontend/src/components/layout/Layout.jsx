import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useLocation, Link, Outlet } from 'react-router-dom';
import { useFilterStore } from '../../store/useFilterStore';
import { useDataStore } from '../../store/useDataStore';
import { useQuery } from '@tanstack/react-query';
import { getCountries, getRegions, getEquipmentTypes, getCompanyNames, loadData, getLoadProgress, getDataStatus } from '../../api/dataApi';
import api from '../../api/client';
import smsLogo from '../../sms logo.png';
import './Layout.css';

const getCompanySelectionLabel = (selectedValue, groupOptions = []) => {
    if (!selectedValue || selectedValue === 'All') {
        return '';
    }

    const selectedGroup = groupOptions.find((group) => group.group_value === selectedValue);
    return selectedGroup?.group_label || selectedValue;
};

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
    const { dataLoaded, setDataLoaded, addLog, clearLogs } = useDataStore();

    // UI fetching
    const [loadingDb, setLoadingDb] = useState(false);
    const [loadProgress, setLoadProgress] = useState(null);
    const [rematching, setRematching] = useState(false);
    const [rematchMsg, setRematchMsg] = useState('');
    const [companySearchTerm, setCompanySearchTerm] = useState('');
    const [activeLoadJobId, setActiveLoadJobId] = useState(null);
    const pollRef = useRef(null);
    const pollInFlightRef = useRef(false);
    const pollFailuresRef = useRef(0);

    // Queries to fetch the filter lists (Countries, Regions, Equipment)
    const { data: regionsList = ['All'] } = useQuery({ queryKey: ['regions'], queryFn: getRegions, enabled: dataLoaded });
    const { data: countriesList = ['All'] } = useQuery({ queryKey: ['countries'], queryFn: getCountries, enabled: dataLoaded });
    const { data: equipmentList = ['All'] } = useQuery({ queryKey: ['equipments'], queryFn: getEquipmentTypes, enabled: dataLoaded });

    // Company Names Query - filtered by current region/country/equipment
    const { data: companyHierarchy = { company_names: [], company_groups: [], standalone_companies: [] } } = useQuery({
        queryKey: ['company_names', { region, country, equipmentType }],
        queryFn: () => getCompanyNames({ region, country, equipment_type: equipmentType }),
        enabled: dataLoaded
    });

    const groupOptions = Array.isArray(companyHierarchy?.company_groups) ? companyHierarchy.company_groups : [];
    const standaloneOptions = Array.isArray(companyHierarchy?.standalone_companies) ? companyHierarchy.standalone_companies : [];
    const allCompanyValues = ['All', ...(companyHierarchy?.company_names || [])];
    const groupValues = groupOptions.map((group) => group.group_value);
    const validCompanyValues = new Set([...allCompanyValues, ...groupValues]);

    const filteredGroupOptions = groupOptions
        .map((group) => {
            const search = companySearchTerm.trim().toLowerCase();
            if (!search) {
                return group;
            }
            const groupMatch = String(group.group_label || '').toLowerCase().includes(search);
            const branchMatch = (group.branches || []).filter((branch) =>
                String(branch.label || '').toLowerCase().includes(search)
            );
            if (groupMatch) {
                return group;
            }
            if (branchMatch.length > 0) {
                return { ...group, branches: branchMatch };
            }
            return null;
        })
        .filter(Boolean);

    const filteredStandaloneOptions = standaloneOptions.filter((item) => {
        if (!companySearchTerm.trim()) return true;
        return String(item.label || '').toLowerCase().includes(companySearchTerm.trim().toLowerCase());
    });

    const totalRenderedOptions =
        1 +
        filteredGroupOptions.reduce((acc, group) => acc + 1 + (group.branches || []).length, 0) +
        filteredStandaloneOptions.length;

    const totalAvailableOptions =
        1 +
        groupOptions.reduce((acc, group) => acc + 1 + (group.branches || []).length, 0) +
        standaloneOptions.length;

    // If an invalid combination occurs, automatically select 'All' for Company Name
    useEffect(() => {
        if (companyName !== 'All' && validCompanyValues.size > 1 && !validCompanyValues.has(companyName)) {
            setCompanyName('All');
        }
    }, [validCompanyValues, companyName, setCompanyName]);

    useEffect(() => {
        setCompanySearchTerm(getCompanySelectionLabel(companyName, groupOptions));
    }, [companyName, groupOptions]);

    // Progress polling
    const stopPolling = useCallback(() => {
        if (pollRef.current) {
            clearTimeout(pollRef.current);
            pollRef.current = null;
        }
        pollInFlightRef.current = false;
        pollFailuresRef.current = 0;
    }, []);

    const startPolling = useCallback((jobId = null) => {
        stopPolling();

        const pollOnce = async () => {
            if (pollInFlightRef.current) {
                pollRef.current = setTimeout(pollOnce, 1200);
                return;
            }

            pollInFlightRef.current = true;
            try {
                const progress = await getLoadProgress(jobId);
                pollFailuresRef.current = 0;
                setLoadProgress(progress);

                if (progress?.job_id) {
                    setActiveLoadJobId(progress.job_id);
                }

                // Sync logs
                if (progress.logs && progress.logs.length > 0) {
                    clearLogs();
                    progress.logs.forEach(addLog);
                }

                if (progress.done) {
                    stopPolling();
                    setLoadingDb(false);
                    if (!progress.error) {
                        setDataLoaded(true);
                    }
                    // Keep progress visible for 3 seconds after completion
                    setTimeout(() => {
                        if (!progress.error) {
                            setLoadProgress(null);
                        }
                    }, 3000);
                    return;
                }
            } catch (err) {
                pollFailuresRef.current += 1;
                if (pollFailuresRef.current % 3 === 0) {
                    console.error("Failed to poll progress:", err);
                }
            } finally {
                pollInFlightRef.current = false;
                // Back off slightly on repeated failures to reduce request pressure.
                const delay = pollFailuresRef.current >= 3 ? 2500 : 1200;
                pollRef.current = setTimeout(pollOnce, delay);
            }
        };

        pollRef.current = setTimeout(pollOnce, 0);
    }, [stopPolling, clearLogs, addLog, setDataLoaded]);

    // Check Data Loaded status on initial app boot
    useEffect(() => {
        const checkStatus = async () => {
            try {
                const status = await getDataStatus();
                const statusJobId = status?.job_id || null;
                const progress = await getLoadProgress(statusJobId).catch(() => null);
                const isReloading = Boolean(progress?.running);

                if (statusJobId) {
                    setActiveLoadJobId(statusJobId);
                }

                if (progress) {
                    setLoadProgress(progress);
                    setLoadingDb(isReloading);
                }

                setDataLoaded(Boolean(status.loaded) && !isReloading);

                if (isReloading) {
                    startPolling(statusJobId || progress?.job_id || null);
                }
            } catch {
                try {
                    const progress = await getLoadProgress(activeLoadJobId);
                    const loadCompleted = Boolean(progress.done && !progress.error);
                    setLoadProgress(progress);
                    setLoadingDb(Boolean(progress.running));
                    setDataLoaded(loadCompleted && !progress.running);

                    if (progress?.job_id) {
                        setActiveLoadJobId(progress.job_id);
                    }

                    if (progress.running) {
                        startPolling(progress.job_id || activeLoadJobId || null);
                    }
                } catch (progressError) {
                    console.error("Failed to fetch data status:", progressError);
                    setDataLoaded(false);
                }
            }
        };
        checkStatus();
    }, [setDataLoaded, startPolling, activeLoadJobId]);

    // Cleanup on unmount
    useEffect(() => {
        return () => stopPolling();
    }, [stopPolling]);

    const handleLoadData = async () => {
        setLoadingDb(true);
        setDataLoaded(false);
        setLoadProgress({ running: true, step: 'Starting...', percent: 0, done: false, error: null, logs: [] });
        clearLogs();
        try {
            const result = await loadData();
            const jobId = result?.job_id || null;
            setActiveLoadJobId(jobId);
            startPolling(jobId);
        } catch (error) {
            // The backend endpoint starts a background job. If this start request
            // times out, the job may still be running: switch to polling instead
            // of failing immediately.
            const isTimeout =
                error?.code === 'ECONNABORTED' ||
                String(error?.message || '').toLowerCase().includes('timeout');

            if (isTimeout) {
                addLog('Load start request timed out. Checking background progress...');
                startPolling(activeLoadJobId);
                return;
            }

            console.error("Failed to load data:", error);
            addLog("Error loading data: " + error.message);
            setLoadingDb(false);
            setLoadProgress({ running: false, step: 'Error', percent: 0, done: true, error: error.message, logs: [] });
        }
    };

    const handleRematchPoor = async () => {
        setRematching(true);
        setRematchMsg('Re-matching poor entries...');
        try {
            const res = await api.post('/data/rematch-poor');
            setRematchMsg(res.data.message || 'Rematch started. Reload data when complete.');
        } catch (error) {
            setRematchMsg('Rematch failed: ' + (error.response?.data?.detail || error.message));
        } finally {
            setRematching(false);
        }
    };


    const navigation = [
        { name: 'Overview', href: '/' },
        { name: 'Priority Ranking', href: '/ranking' },
        { name: 'Customer Profile', href: '/customer' },
    ];

    const effectiveProgress = loadProgress || (dataLoaded
        ? { running: false, done: true, step: 'Data loaded', percent: 100, error: null }
        : null);

    return (
        <div className="app-container">
            {/* Sidebar */}
            <aside className="sidebar">
                <div className="sidebar-header">
                    <img src="/logo.png" alt="SMS group" className="logo" onError={(e) => e.target.style.display = 'none'} />
                </div>

                <nav className="nav-menu">
                    <img src={smsLogo} alt="SMS logo" className="navigation-logo" />
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
                                    {regionsList.filter(i => i !== 'All').map(item => <option key={item} value={item}>{item}</option>)}
                                </select>
                            </div>

                            <div className="form-group">
                                <label>Country</label>
                                <select value={country} onChange={(e) => setCountry(e.target.value)}>
                                    <option value="All">All</option>
                                    {countriesList.filter(i => i !== 'All').map(item => <option key={item} value={item}>{item}</option>)}
                                </select>
                            </div>

                            <div className="form-group">
                                <label>Equipment Type</label>
                                <select value={equipmentType} onChange={(e) => setEquipmentType(e.target.value)}>
                                    <option value="All">All</option>
                                    {equipmentList.filter(i => i !== 'All').map(item => <option key={item} value={item}>{item}</option>)}
                                </select>
                            </div>

                            <div className="form-group">
                                <label>Company Name</label>
                                <input
                                    type="text"
                                    className="company-search-input"
                                    placeholder="Search company..."
                                    value={companySearchTerm}
                                    onChange={(e) => setCompanySearchTerm(e.target.value)}
                                />
                                <select
                                    value={companyName}
                                    onChange={(e) => {
                                        const selected = e.target.value;
                                        setCompanyName(selected);
                                        setCompanySearchTerm(getCompanySelectionLabel(selected, groupOptions));
                                    }}
                                    title="Deep dive into a specific customer"
                                >
                                    <option value="All">All</option>

                                    {filteredGroupOptions.map((group) => (
                                        <optgroup
                                            key={group.group_key}
                                            label={`${group.group_label} (${group.branch_count} branches)`}
                                        >
                                            <option value={group.group_value}>{group.group_label} (All branches)</option>
                                            {(group.branches || []).map((branch) => (
                                                <option key={`${group.group_key}-${branch.value}`} value={branch.value}>
                                                    {'  '}• {branch.label}
                                                </option>
                                            ))}
                                        </optgroup>
                                    ))}

                                    {filteredStandaloneOptions.length > 0 && (
                                        <optgroup label="Standalone Companies">
                                            {filteredStandaloneOptions.map((item) => (
                                                <option key={item.value} value={item.value}>{item.label}</option>
                                            ))}
                                        </optgroup>
                                    )}
                                </select>
                                <div className="company-filter-hint">Showing {totalRenderedOptions} of {totalAvailableOptions} company options</div>
                            </div>
                        </div>
                    )}
                </div>

                <div className="sidebar-divider"></div>

                <div className="settings-section">
                    <h3 className="sidebar-section-title">Settings</h3>
                    <div className="data-management">
                        <h4>Data Management</h4>
                        {dataLoaded && !loadingDb && <div className="success-box">Data is loaded</div>}

                        {/* Progress Bar */}
                        {effectiveProgress && (effectiveProgress.running || effectiveProgress.done) && (
                            <div className="load-progress-container">
                                <div className="load-progress-step">{effectiveProgress.step}</div>
                                <div className="load-progress-bar-track">
                                    <div
                                        className={`load-progress-bar-fill ${effectiveProgress.done && !effectiveProgress.error ? 'complete' : ''} ${effectiveProgress.error ? 'error' : ''}`}
                                        style={{ width: `${effectiveProgress.percent}%` }}
                                    />
                                </div>
                                <div className="load-progress-percent">{effectiveProgress.percent}%</div>
                                {effectiveProgress.error && (
                                    <div className="load-progress-error">{effectiveProgress.error}</div>
                                )}
                            </div>
                        )}

                        <button
                            className="btn-primary load-btn"
                            onClick={handleLoadData}
                            disabled={loadingDb}
                        >
                            {loadingDb ? 'Loading...' : 'Load Data'}
                        </button>

                        {dataLoaded && (
                            <>
                                <button
                                    className="btn-secondary load-btn"
                                    style={{ marginTop: '0.5rem', fontSize: '0.78rem', background: 'var(--surface-hover)', color: 'var(--accent)', border: '1px solid var(--accent)' }}
                                    onClick={handleRematchPoor}
                                    disabled={rematching || loadingDb}
                                    title="Re-match all poor/unmatched company entries using LLM + web search"
                                >
                                    {rematching ? '🔄 Re-matching...' : '🔍 Rematch Poor Entries'}
                                </button>
                                {rematchMsg && <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '0.35rem', lineHeight: '1.4' }}>{rematchMsg}</div>}
                            </>
                        )}
                    </div>


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
