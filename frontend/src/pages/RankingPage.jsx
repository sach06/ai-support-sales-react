import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useFilterStore } from '../store/useFilterStore';
import { useDataStore } from '../store/useDataStore';
import { getRankedList, getModelStatus } from '../api/rankingApi';

import RankingTable from './RankingTable';
import RankingExplainer from './RankingExplainer';
import RankingCharts from './RankingCharts';
import './Ranking.css';

const RankingPage = () => {
    const { country, equipmentType, companyName } = useFilterStore();
    const { dataLoaded } = useDataStore();

    const [selectedCompany, setSelectedCompany] = useState(null);
    const [forceHeuristic, setForceHeuristic] = useState(false);

    // Fetch ML Model Availability Status
    const { data: statusData } = useQuery({
        queryKey: ['model_status'],
        queryFn: getModelStatus,
        enabled: dataLoaded,
    });

    // Main Ranking List Query based on sidebar filters via API
    const { data: rankings, isLoading, isError } = useQuery({
        queryKey: ['ranked_list', { equipmentType, country, forceHeuristic }],
        queryFn: () => getRankedList({ equipmentType, country, topK: 50, forceHeuristic }),
        enabled: dataLoaded,
    });

    const isModelAvailable = statusData?.available || false;

    // Fallback switch boolean condition
    const isUsingHeuristic = !isModelAvailable || forceHeuristic;

    if (!dataLoaded) {
        return (
            <div className="ranking-empty-state">
                <h2>Priority Ranking</h2>
                <p>Please load data from the side menu to view rankings.</p>
            </div>
        );
    }

    // Auto-select the company in focus if it exists in the ranking set, otherwise pick the top rank.
    useEffect(() => {
        if (rankings && rankings.length > 0) {
            if (companyName && companyName !== 'All') {
                const target = rankings.find(r => r.company.toLowerCase() === companyName.toLowerCase());
                if (target) {
                    setSelectedCompany(target);
                    return;
                }
            }
            // If target isn't explicitly found, keep current selection, 
            // but if we have no selection yet, gracefully default to the first
            if (!selectedCompany && rankings[0]) {
                setSelectedCompany(rankings[0]);
            }
        }
    }, [rankings, companyName]);

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

                {isModelAvailable && (
                    <div className="banner-actions">
                        <label className="toggle-label">
                            <input
                                type="checkbox"
                                checked={forceHeuristic}
                                onChange={(e) => setForceHeuristic(e.target.checked)}
                            />
                            Force Heuristic Rules
                        </label>
                    </div>
                )}
            </div>

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
                            data={rankings || []}
                            onRowSelect={setSelectedCompany}
                            selectedId={selectedCompany?.company}
                            pinnedCompany={companyName}
                        />
                    )}
                </div>

                <div className="explainer-section">
                    <h3>Company Explainer</h3>
                    <div className="explainer-panel">
                        <RankingExplainer rowData={selectedCompany} />
                    </div>
                </div>
            </div>

            {/* Charts Section */}
            <div className="ranking-charts-section">
                <h3>Analytics & Breakdown</h3>
                <div className="charts-panel">
                    <RankingCharts data={rankings || []} />
                </div>
            </div>
        </div>
    );
};

export default RankingPage;
