import React from 'react';

const RankingExplainer = ({ rowData }) => {
    if (!rowData) return <div className="explainer-empty">Select a company from the ranking table to see details.</div>;

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

    // Helper to format feature names for readability
    const formatFeatureName = (name) => {
        return name.replace(/_/g, ' ')
            .replace(/\b\w/g, l => l.toUpperCase());
    };

    return (
        <div className="ranking-explainer">
            <div className="explainer-header">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h3 className="company-name">{rowData.company_name}</h3>
                    <div className="big-score">{(rowData.score * 100).toFixed(1)}</div>
                </div>
                {rowData.country && <div className="company-meta">{rowData.country} • {rowData.equipment_type || 'Mixed Equipment'}</div>}
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
                            </li>
                        ))}
                    </ul>
                )}

                <div className="action-button-container">
                    {/* Note: This logic would be hooked up to React Router in actual usage to redirect */}
                    <button className="btn-primary" onClick={() => alert(`Redirect to customer profile for ${rowData.company_name}`)}>
                        View Full Profile
                    </button>
                </div>
            </div>
        </div>
    );
};

export default RankingExplainer;
