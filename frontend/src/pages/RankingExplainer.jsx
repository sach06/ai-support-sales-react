import React, { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../api/client';

const fetchCompanyNews = async (company, equipmentType, country) => {
    const response = await api.get('/data/news', {
        params: {
            company,
            equipment_type: equipmentType,
            country,
            limit: 6,
        },
    });
    return response.data?.news || [];
};

const RankingExplainer = ({ rowData }) => {
    if (!rowData) return <div className="explainer-empty">Select a company from the ranking table to see details.</div>;

    const DEFAULT_TOP_DRIVERS = [
        { name: 'equipment_age', impact: 1.0 },
        { name: 'is_sms_oem', impact: 0.85 },
        { name: 'crm_rating_num', impact: 0.8 },
        { name: 'crm_projects_count', impact: 0.75 },
        { name: 'log_fte', impact: 0.7 },
    ];

    const DRIVER_EXPLANATIONS = {
        equipment_age: 'Older assets usually have higher modernization pressure and stronger replacement economics.',
        is_sms_oem: 'Installed SMS footprint increases compatibility and usually lowers implementation risk.',
        crm_rating_num: 'A stronger relationship score often means faster qualification and better sponsor access.',
        crm_projects_count: 'More historical projects indicate execution trust and clear upsell pathways.',
        log_fte: 'Larger organizations tend to run broader capex programs and continuous improvement roadmaps.',
        equipment_type_enc: 'Equipment class is a structural predictor of lifecycle needs and technical intervention depth.',
        country_enc: 'Country context captures macro and policy effects that influence investment timing.',
        knowledge_doc_count: 'Number of relevant SMS references found for this customer. More references usually means a warmer start.',
        knowledge_best_match_score: 'How strong our single best historical SMS match is. Higher means very similar proven work.',
        knowledge_avg_match_score: 'How relevant our matched references are overall. Higher means stronger overall fit.',
        knowledge_service_signal: 'Service-heavy evidence points to maintenance contracts, spares demand, and service-led sales entry.',
        knowledge_inspection_signal: 'Inspection evidence indicates technical touchpoints that can convert into modernization projects.',
        knowledge_modernization_signal: 'Revamp-heavy signals suggest meaningful capex potential and modernization demand.',
        knowledge_digital_signal: 'Digital references indicate opportunities in automation, optimization, and performance analytics.',
        knowledge_decarbonization_signal: 'Decarbonization evidence supports positioning around EAF, emissions reduction, and green steel pathways.',
        knowledge_project_signal: 'Project-level evidence increases confidence that active execution or commercial momentum exists.',
        knowledge_quality_signal: 'Quality-related evidence may indicate corrective retrofit, reliability, and lifecycle service opportunities.',
        ext_news_capex_signal: 'Stable public-news aggregates indicate capex or expansion activity around this account.',
        ext_news_modernization_signal: 'Stable public signals suggest upgrade or modernization momentum.',
        ext_news_decarbonization_signal: 'Stable public signals suggest decarbonization relevance in the account narrative.',
        market_country_trade_pressure_score: 'Country-level trade pressure can change competitiveness and the timing of investment decisions.',
        market_country_macro_activity_score: 'Country macro activity influences whether industrial customers are likely to fund upgrades.',
    };

    const DRIVER_LABELS = {
        equipment_age: 'Equipment age and replacement timing',
        is_sms_oem: 'Existing SMS footprint at site',
        crm_rating_num: 'Relationship strength in CRM',
        crm_projects_count: 'Past projects with this account',
        log_fte: 'Customer size and investment capacity',
        equipment_type_enc: 'Equipment lifecycle profile',
        country_enc: 'Country market and policy context',
        knowledge_doc_count: 'How many relevant SMS references we found',
        knowledge_best_match_score: 'Best historical SMS match quality',
        knowledge_avg_match_score: 'Overall historical match quality',
        knowledge_service_signal: 'Service follow-up potential',
        knowledge_inspection_signal: 'Inspection-led entry potential',
        knowledge_modernization_signal: 'Modernization potential',
        knowledge_digital_signal: 'Digital optimization potential',
        knowledge_decarbonization_signal: 'Decarbonization potential',
        knowledge_project_signal: 'Active project momentum',
        knowledge_quality_signal: 'Quality-improvement opportunity',
        ext_news_capex_signal: 'Stable capex news signal',
        ext_news_modernization_signal: 'Stable modernization news signal',
        ext_news_decarbonization_signal: 'Stable decarbonization news signal',
        market_country_trade_pressure_score: 'Country trade-pressure context',
        market_country_macro_activity_score: 'Country macro activity',
    };

    const { data: newsItems = [] } = useQuery({
        queryKey: ['ranking_company_news', rowData.company, rowData.equipment_type, rowData.country],
        queryFn: () => fetchCompanyNews(rowData.company, rowData.equipment_type, rowData.country),
        staleTime: 300000,
    });

    // The backend ML service returns a JSON string inside the 'top_features' column for XGBoost
    // or a string list for heuristics.
    let parsedFeatures = [];
    try {
        if (typeof rowData.top_features === 'string' && rowData.top_features.startsWith('{')) {
            const featureDict = JSON.parse(rowData.top_features);
            parsedFeatures = Object.entries(featureDict)
                .map(([name, val]) => ({ name, impact: val }))
                .sort((a, b) => b.impact - a.impact)
                .slice(0, 5); // top 5
        } else if (typeof rowData.top_features === 'string') {
            // Heuristic comma-separated
            parsedFeatures = rowData.top_features.split(',').map(f => ({ name: f.trim(), impact: 0 }));
        }
    } catch (e) {
        console.error("Failed to parse features", e);
    }

    if (parsedFeatures.length === 0) {
        parsedFeatures = DEFAULT_TOP_DRIVERS;
    }

    const actionInsights = useMemo(() => {
        const insights = [];
        const age = Number(rowData.equipment_age || 0);
        const serviceSignal = Number(rowData.knowledge_service_signal || 0);
        const modernizationSignal = Number(rowData.knowledge_modernization_signal || 0);
        const decarbSignal = Number(rowData.knowledge_decarbonization_signal || 0);
        const digitalSignal = Number(rowData.knowledge_digital_signal || 0);
        const projectSignal = Number(rowData.knowledge_project_signal || 0);

        if (age >= 18) {
            insights.push(`Aging equipment profile (${age.toFixed(1)} years) supports a modernization-led pitch with staged capex and uptime guarantees.`);
        } else {
            insights.push(`Modern equipment profile (${age.toFixed(1)} years) supports a service-led growth path: predictive maintenance, spares optimization, and performance contracts.`);
        }

        if (decarbSignal >= 0.35) {
            insights.push('Decarbonization signals are elevated. Position energy optimization, electrification enablers, and CO2-reduction retrofits with clear ROI per ton.' );
        }

        if (modernizationSignal >= 0.35 || projectSignal >= 0.35) {
            insights.push('Internal project evidence indicates active technical momentum. Propose a focused site assessment to convert current touchpoints into executable upgrade packages.');
        }

        if (serviceSignal >= 0.35 || digitalSignal >= 0.35) {
            insights.push('Strong service and digital fingerprints suggest immediate value from reliability analytics, maintenance planning, and long-term service agreements.');
        }

        const geopoliticalTitle = newsItems.find((item) => {
            const title = (item.title || '').toLowerCase();
            return title.includes('middle east') || title.includes('war') || title.includes('tariff') || title.includes('sanction');
        });

        if (geopoliticalTitle) {
            insights.push('Recent geopolitical headlines indicate volatility risk in steel value chains. Use risk-mitigation messaging: efficiency upgrades, yield protection, and flexible sourcing-compatible process windows.');
        }

        return insights.slice(0, 5);
    }, [newsItems, rowData]);

    // Helper to format feature names for readability
    const formatFeatureName = (name) => {
        if (DRIVER_LABELS[name]) return DRIVER_LABELS[name];
        return name.replace(/_/g, ' ')
            .replace(/\b\w/g, l => l.toUpperCase());
    };

    const toEvidenceLevel = (score) => {
        if (score >= 8) return 'Very strong';
        if (score >= 6) return 'Strong';
        if (score >= 4) return 'Moderate';
        if (score > 0) return 'Early signal';
        return 'No match yet';
    };

    const knowledgeSignals = [
        { key: 'knowledge_service_signal', label: 'Service' },
        { key: 'knowledge_inspection_signal', label: 'Inspection' },
        { key: 'knowledge_modernization_signal', label: 'Modernization' },
        { key: 'knowledge_digital_signal', label: 'Digital' },
        { key: 'knowledge_decarbonization_signal', label: 'Decarbonization' },
        { key: 'knowledge_project_signal', label: 'Project' },
        { key: 'knowledge_quality_signal', label: 'Quality' },
    ];

    return (
        <div className="ranking-explainer">
            <div className="explainer-header">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h3 className="company-name">{rowData.company}</h3>
                    <div className="big-score" title="Model confidence score">
                        {typeof rowData.priority_score === 'number' ? `${rowData.priority_score.toFixed(1)}%` : '0.0%'}
                    </div>
                </div>
                {rowData.country && <div className="company-meta">{rowData.country} • {rowData.equipment_type || 'Mixed Equipment'}</div>}
                <div className="company-meta">Confidence / Priority Likelihood</div>
                {typeof rowData.base_priority_score === 'number' && (
                    <div className="company-meta">
                        Base {rowData.base_priority_score.toFixed(1)}%
                        {typeof rowData.rerank_adjustment === 'number' ? ` • Recent signal adj. ${rowData.rerank_adjustment >= 0 ? '+' : ''}${rowData.rerank_adjustment.toFixed(1)}` : ''}
                    </div>
                )}
            </div>

            <div className="explainer-body">
                <h4>Actionable Opportunity Insights</h4>
                {actionInsights.length > 0 ? (
                    <ul className="feature-list">
                        {actionInsights.map((insight, idx) => (
                            <li key={`insight-${idx}`}>
                                <div style={{ fontSize: '0.88rem', color: 'var(--text-primary)', lineHeight: '1.45' }}>{insight}</div>
                            </li>
                        ))}
                    </ul>
                ) : null}

                <h4>Why This Account Is High Priority</h4>
                {parsedFeatures.length === 0 ? (
                    <p className="no-features-msg">No specific drivers identified for this score.</p>
                ) : (
                    <ul className="feature-list">
                        {parsedFeatures.map((feat, idx) => (
                            <li key={idx}>
                                <div className="feature-row">
                                    <span className="feature-name">{formatFeatureName(feat.name)}</span>
                                    {feat.impact > 0 && (
                                        <div className="impact-bar-container">
                                            <div
                                                className="impact-bar"
                                                style={{ width: `${Math.min(100, feat.impact * 200)}%` }}
                                            />
                                        </div>
                                    )}
                                </div>
                                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                                    {(rowData.driver_explanations && rowData.driver_explanations[feat.name]) || DRIVER_EXPLANATIONS[feat.name] || 'Core model driver influencing predicted opportunity potential.'}
                                </div>
                            </li>
                        ))}
                    </ul>
                )}

                {Array.isArray(rowData.rerank_reasons) && rowData.rerank_reasons.length > 0 && (
                    <>
                        <h4 style={{ marginTop: '1.25rem' }}>Recent Signal Adjustment</h4>
                        <div style={{ display: 'grid', gap: '0.4rem' }}>
                            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                                Adjustment applied: {typeof rowData.rerank_adjustment === 'number' ? `${rowData.rerank_adjustment >= 0 ? '+' : ''}${rowData.rerank_adjustment.toFixed(1)} pts` : '0.0 pts'}
                            </div>
                            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                                Recent mentions: {Number(rowData.rerank_recent_mentions || 0)} across {Number(rowData.rerank_recent_sources || 0)} sources.
                            </div>
                            <ul className="feature-list">
                                {rowData.rerank_reasons.map((reason, idx) => (
                                    <li key={`rerank-${idx}`}>
                                        <div style={{ fontSize: '0.84rem', color: 'var(--text-primary)' }}>{reason}</div>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    </>
                )}

                <h4 style={{ marginTop: '1.25rem' }}>How to Read the SMS Evidence</h4>
                <div style={{ display: 'grid', gap: '0.5rem' }}>
                    <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                        Relevant SMS references: {Math.round(Number(rowData.knowledge_doc_count || 0))} | Best historical match: {toEvidenceLevel(Number(rowData.knowledge_best_match_score || 0))}
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                        Quick guide: "Best historical match" = closest proven SMS case, "Overall fit" = average similarity across all references.
                    </div>
                    {knowledgeSignals.map((signal) => {
                        const value = Number(rowData[signal.key] || 0);
                        return (
                            <div key={signal.key} style={{ display: 'grid', gridTemplateColumns: '130px 1fr 50px', alignItems: 'center', gap: '0.5rem' }}>
                                <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{signal.label}</span>
                                <div style={{ background: 'rgba(31, 71, 136, 0.08)', height: '8px', borderRadius: '999px', overflow: 'hidden' }}>
                                    <div style={{ width: `${Math.round(value * 100)}%`, height: '100%', background: 'linear-gradient(90deg, var(--primary), var(--secondary))' }} />
                                </div>
                                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{Math.round(value * 100)}%</span>
                            </div>
                        );
                    })}
                    {rowData.knowledge_summary && (
                        <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>{rowData.knowledge_summary}</div>
                    )}
                </div>

                <h4 style={{ marginTop: '1.25rem' }}>Market And Geopolitical Pulse</h4>
                {newsItems.length === 0 ? (
                    <p className="no-features-msg">No recent contextual news fetched for this account.</p>
                ) : (
                    <ul className="feature-list" style={{ marginBottom: '1rem' }}>
                        {newsItems.slice(0, 3).map((item, idx) => (
                            <li key={`news-${idx}`}>
                                <div style={{ fontSize: '0.85rem', color: 'var(--text-primary)', lineHeight: '1.35' }}>
                                    {item.title}
                                </div>
                                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                                    {item.source || 'Unknown source'}
                                </div>
                            </li>
                        ))}
                    </ul>
                )}

                <div className="action-button-container">
                    {/* Note: This logic would be hooked up to React Router in actual usage to redirect */}
                    <button className="btn-primary" onClick={() => alert(`Redirect to customer profile for ${rowData.company}`)}>
                        View Full Profile
                    </button>
                </div>
            </div>
        </div>
    );
};

export default RankingExplainer;
