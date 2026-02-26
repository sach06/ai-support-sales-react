import React from 'react';

const MetricCard = ({ title, value, subtitle, colorClass = "" }) => {
    return (
        <div className={`metric-card ${colorClass}`}>
            <h4 className="metric-title">{title}</h4>
            <div className="metric-value">{value}</div>
            <div className="metric-subtitle">{subtitle}</div>
        </div>
    );
};

export default MetricCard;
