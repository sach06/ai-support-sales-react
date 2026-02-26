import React from 'react';

const OpportunityBadge = ({ type }) => {
    let mapping = {
        'OEM Replacement': { color: '#007020', bg: 'rgba(0, 112, 32, 0.1)', icon: '🔄' },
        'Revamping / Upgrade': { color: '#38a169', bg: 'rgba(56, 161, 105, 0.1)', icon: '⚡' },
        'New Build / Capacity Expansion': { color: '#2b6cb0', bg: 'rgba(43, 108, 176, 0.1)', icon: '🏗️' },
        'Service Contract': { color: '#d69e2e', bg: 'rgba(214, 158, 46, 0.1)', icon: '🛠️' },
        'Heuristic Analysis': { color: '#718096', bg: 'rgba(113, 128, 150, 0.1)', icon: '🧠' }
    };

    const style = mapping[type] || { color: '#718096', bg: 'rgba(113, 128, 150, 0.1)', icon: '🏷️' };

    return (
        <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.25rem',
            padding: '0.25rem 0.6rem',
            borderRadius: '12px',
            fontSize: '0.75rem',
            fontWeight: '600',
            color: style.color,
            backgroundColor: style.bg
        }}>
            <span>{style.icon}</span>
            {type}
        </span>
    );
};

export default OpportunityBadge;
