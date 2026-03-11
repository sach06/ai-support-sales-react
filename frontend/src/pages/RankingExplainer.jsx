import React from 'react';

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
    };

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

    // Helper to format feature names for readability
    const formatFeatureName = (name) => {
        return name.replace(/_/g, ' ')
            .replace(/\b\w/g, l => l.toUpperCase());
    };

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
            </div>

            <div className="explainer-body">
                <h4>Top Drivers for Priority</h4>
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
