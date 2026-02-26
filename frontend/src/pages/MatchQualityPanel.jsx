import React from 'react';

const MatchQualityPanel = ({ data }) => {
    // Group identically to the python backend Logic for match comparison
    const matchGroups = data.reduce((acc, plant) => {
        const type = plant.match_type || 'Poor';
        acc[type] = acc[type] || [];
        acc[type].push(plant);
        return acc;
    }, {});

    const orderedStatus = ['Excellent', 'Good', 'Okay', 'Poor'];

    return (
        <div style={{ marginTop: '1rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                This table shows the link quality between the CRM system details and the BCG planted machine details. Good links indicate highly reliable historical data.
            </p>
            {orderedStatus.map(status => {
                const groupData = matchGroups[status] || [];
                const percentage = data.length > 0 ? ((groupData.length / data.length) * 100).toFixed(1) : 0;

                return (
                    <div key={status} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.75rem', border: '1px solid var(--border)', borderRadius: '6px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <span className={`badge badge-${status.toLowerCase()}`}>{status}</span>
                            <span style={{ fontSize: '0.9rem', color: 'var(--text-primary)', fontWeight: '500' }}>
                                {groupData.length} records
                            </span>
                        </div>
                        <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: '600' }}>
                            {percentage}%
                        </span>
                    </div>
                );
            })}
        </div>
    );
};

export default MatchQualityPanel;
