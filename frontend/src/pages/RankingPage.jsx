import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useFilterStore } from '../store/useFilterStore';
import { useDataStore } from '../store/useDataStore';
import { getRankedList, getModelStatus, retrainRankingModel, getRetrainStatus, refreshExternalFeatures } from '../api/rankingApi';

import RankingTable from './RankingTable';
import RankingExplainer from './RankingExplainer';
import RankingCharts from './RankingCharts';
import './Ranking.css';

const normalizeCompanyName = (name) => {
    if (!name) return '';
    return String(name)
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/[^a-zA-Z0-9]/g, '')
        .toLowerCase();
};

const isCompanyMatch = (candidate, target) => {
    const a = normalizeCompanyName(candidate);
    const b = normalizeCompanyName(target);
    if (!a || !b) return false;
    return a === b || a.startsWith(b) || b.startsWith(a) || a.includes(b) || b.includes(a);
};

const GROUP_PREFIX = 'group::';

const RankingPage = () => {
    const { country, equipmentType, companyName } = useFilterStore();
    const { dataLoaded } = useDataStore();

    const [selectedCompany, setSelectedCompany] = useState(null);
    const [forceHeuristic, setForceHeuristic] = useState(false);
    const [isRetraining, setIsRetraining] = useState(false);
    const [isRefreshingExternal, setIsRefreshingExternal] = useState(false);
    const [retrainMessage, setRetrainMessage] = useState(null);
    const [retrainSuccess, setRetrainSuccess] = useState(null); // true | false | null
    const retrainPollRef = useRef(null);

    // Clear polling on unmount
    useEffect(() => () => { if (retrainPollRef.current) clearInterval(retrainPollRef.current); }, []);

    const _startPollingRetrain = () => {
        if (retrainPollRef.current) clearInterval(retrainPollRef.current);
        retrainPollRef.current = setInterval(async () => {
            try {
                const s = await getRetrainStatus();
                if (s.status === 'done') {
                    clearInterval(retrainPollRef.current);
                    retrainPollRef.current = null;
                    setIsRetraining(false);
                    setRetrainSuccess(true);
                    const auc = s.result?.metrics?.auc_test;
                    setRetrainMessage(
                        `Model retrained on ${s.result?.sample_count || 0} samples, ` +
                        `${s.result?.feature_count || 0} features` +
                        (typeof auc === 'number' ? ` · AUC ${auc.toFixed(3)}` : '') + '.'
                    );
                    await refetchStatus();
                    await refetchRankings();
                    setForceHeuristic(false);
                } else if (s.status === 'error') {
                    clearInterval(retrainPollRef.current);
                    retrainPollRef.current = null;
                    setIsRetraining(false);
                    setRetrainSuccess(false);
                    setRetrainMessage(`Retraining failed: ${s.message}`);
                }
            } catch (_) { /* ignore transient errors */ }
        }, 2500);
    };

    // Fetch ML Model Availability Status
    const { data: statusData, refetch: refetchStatus } = useQuery({
        queryKey: ['model_status'],
        queryFn: getModelStatus,
        enabled: dataLoaded,
        staleTime: 120_000,
    });

    // Main Ranking List Query based on sidebar filters via API
    const { data: rankings, isLoading, isError, error: rankingError, refetch: refetchRankings } = useQuery({
        queryKey: ['ranked_list', { equipmentType, country, companyName, forceHeuristic }],
        queryFn: () => getRankedList({
            equipmentType,
            country,
            companyName,
            topK: 50,
            forceHeuristic,
        }),
        enabled: dataLoaded,
        staleTime: 60_000,
    });

    const isModelAvailable = statusData?.available || false;
    const selectedGroupKey = companyName?.startsWith(GROUP_PREFIX)
        ? companyName.slice(GROUP_PREFIX.length)
        : null;

    // Fallback switch boolean condition
    const isUsingHeuristic = !isModelAvailable || forceHeuristic;

    const handleRetrain = async () => {
        setIsRetraining(true);
        setRetrainMessage('Retraining started...');
        setRetrainSuccess(null);
        try {
            await retrainRankingModel('live_duckdb_internal_knowledge');
            _startPollingRetrain();
        } catch (err) {
            console.error('Failed to start retraining:', err);
            setRetrainMessage('Failed to start retraining. Check backend logs.');
            setRetrainSuccess(false);
            setIsRetraining(false);
        }
    };

    const handleRefreshExternalFeatures = async () => {
        setIsRefreshingExternal(true);
        setRetrainMessage('Refreshing stable external features...');
        setRetrainSuccess(null);
        try {
            const result = await refreshExternalFeatures(75);
            setRetrainSuccess(true);
            setRetrainMessage(
                `External features refreshed: ${result.company_feature_rows || 0} company rows, ${result.country_feature_rows || 0} country rows.`
            );
            await refetchRankings();
        } catch (err) {
            console.error('Failed to refresh external features:', err);
            const detail = err?.response?.data?.detail || err?.message || 'Unknown error';
            setRetrainSuccess(false);
            setRetrainMessage(`External feature refresh failed: ${detail}`);
        } finally {
            setIsRefreshingExternal(false);
        }
    };

    // Auto-select the company in focus if it exists in the ranking set, otherwise pick the top rank.
    useEffect(() => {
        if (!rankings || rankings.length === 0) {
            setSelectedCompany(null);
            return;
        }

        if (companyName && companyName !== 'All') {
            const target = selectedGroupKey
                ? rankings.find((r) => String(r.company_group_key || '') === selectedGroupKey)
                : rankings.find((r) => isCompanyMatch(r.company, companyName));
            if (target) {
                setSelectedCompany(target);
                return;
            }
        }

        if (selectedCompany) {
            const updatedSelected = rankings.find((r) => r.company === selectedCompany.company);
            if (updatedSelected) {
                setSelectedCompany(updatedSelected);
                return;
            }
        }

        setSelectedCompany(rankings[0]);
    }, [rankings, companyName, selectedGroupKey, selectedCompany]);

    const displayRankings = useMemo(() => {
        if (!rankings || rankings.length === 0) return [];

        const rankedWithOriginal = rankings.map((row, index) => ({
            ...row,
            original_rank: index + 1,
            display_rank: index + 1,
        }));

        if (!companyName || companyName === 'All') {
            return rankedWithOriginal;
        }

        if (selectedGroupKey) {
            const pinnedRows = rankedWithOriginal.filter(
                (row) => String(row.company_group_key || '') === selectedGroupKey
            );
            if (pinnedRows.length === 0) {
                return rankedWithOriginal;
            }
            const pinnedCompanySet = new Set(pinnedRows.map((row) => row.company));
            const others = rankedWithOriginal.filter((row) => !pinnedCompanySet.has(row.company));
            return [
                ...pinnedRows.map((row) => ({ ...row, display_rank: 0 })),
                ...others.map((row, idx) => ({ ...row, display_rank: idx + 1 })),
            ];
        }

        const targetIndex = rankedWithOriginal.findIndex(
            (row) => isCompanyMatch(row.company, companyName)
        );
        if (targetIndex < 0) {
            return rankedWithOriginal;
        }

        const pinned = rankedWithOriginal[targetIndex];
        const others = rankedWithOriginal.filter((_, idx) => idx !== targetIndex);
        return [
            { ...pinned, display_rank: 0 },
            ...others.map((row, idx) => ({ ...row, display_rank: idx + 1 })),
        ];
    }, [rankings, companyName, selectedGroupKey]);

    const pinnedCompanyLabel = selectedGroupKey
        ? (displayRankings.find((row) => String(row.company_group_key || '') === selectedGroupKey)?.company_group_label || companyName)
        : companyName;

    if (!dataLoaded) {
        return (
            <div className="ranking-empty-state">
                <h2>Priority Ranking</h2>
                <p>Please load data from the side menu to view rankings.</p>
            </div>
        );
    }

    return (
        <div className="ranking-container">
            {/* Header Banner */}
            <div className={`status-banner ${isUsingHeuristic ? 'banner-warning' : 'banner-success'}`}>
                <div className="banner-content">
                    <span className="banner-icon">{isUsingHeuristic ? '⚠️' : '✅'}</span>
                    <div className="banner-text">
                        <strong>Scoring Engine: </strong>
                        {isUsingHeuristic ? 'Heuristic Rules (Fallback Mode)' : 'XGBoost ML Model Active'}
                    </div>
                </div>

                <div className="banner-actions">
                    {isModelAvailable && (
                        <label className="toggle-label">
                            <input
                                type="checkbox"
                                checked={forceHeuristic}
                                onChange={(e) => setForceHeuristic(e.target.checked)}
                            />
                            Force Heuristic Rules
                        </label>
                    )}
                    <button className="btn-secondary" onClick={handleRefreshExternalFeatures} disabled={isRefreshingExternal || isRetraining}>
                        {isRefreshingExternal ? 'Refreshing External Features...' : 'Refresh External Features'}
                    </button>
                    <button className="btn-secondary" onClick={handleRetrain} disabled={isRetraining}>
                        {isRetraining ? 'Retraining...' : 'Retrain Model'}
                    </button>
                </div>
            </div>

            {retrainMessage && (
                <div className={`status-banner ${retrainSuccess === false ? 'banner-warning' : 'banner-success'}`} style={{ marginBottom: '1rem' }}>
                    <div className="banner-content">
                        <span className="banner-icon">{retrainSuccess === false ? '❌' : '🧠'}</span>
                        <div className="banner-text">{retrainMessage}</div>
                    </div>
                </div>
            )}

            {/* Explainer + Rankings Table Split */}
            <div className="ranking-main-split">
                <div className="table-section">
                    <h3>Top Opportunities</h3>
                    {isLoading ? (
                        <div className="loading-state">Scoring companies...</div>
                    ) : isError ? (
                        <div className="error-state">Failed to calculate rankings.</div>
                    ) : (
                        <RankingTable
                            data={displayRankings}
                            onRowSelect={setSelectedCompany}
                            selectedId={selectedCompany?.company}
                            pinnedCompany={pinnedCompanyLabel}
                            pinnedGroupKey={selectedGroupKey}
                        />
                    )}
                </div>

                <div className="explainer-section">
                    <h3>Company Explainer</h3>
                    <div className="explainer-panel">
                        <RankingExplainer
                            rowData={selectedCompany}
                            rankingError={isError ? rankingError : null}
                            filterContext={{ country, equipmentType, companyName }}
                        />
                    </div>
                </div>
            </div>

            {/* Charts Section */}
            <div className="ranking-charts-section">
                <h3>Opportunity Breakdown, Win/Loss & Competitor Deep Dive</h3>
                <div className="charts-panel">
                    <RankingCharts data={displayRankings} selectedCompany={selectedCompany} />
                </div>
            </div>
        </div>
    );
};

export default RankingPage;
