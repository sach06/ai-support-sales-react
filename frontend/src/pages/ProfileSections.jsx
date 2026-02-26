import React, { useState } from 'react';

const ProfileSections = ({ profile }) => {
    const [activeTab, setActiveTab] = useState('basic');

    if (!profile) return null;

    const tabs = [
        { id: 'basic', label: 'Basic Data' },
        { id: 'locations', label: 'Locations & Setup' },
        { id: 'history', label: 'Background & History' },
        { id: 'financial', label: 'Financial Status' },
        { id: 'strategy', label: 'Customer Strategy' },
    ];

    const renderBasicData = () => (
        <div className="tab-content basic-data-grid">
            <div className="data-group">
                <h4>Legal Name</h4>
                <p>{profile.company_name || 'N/A'}</p>
            </div>
            <div className="data-group">
                <h4>Country / Region</h4>
                <p>{profile.main_country || 'N/A'}</p>
            </div>
            <div className="data-group">
                <h4>Primary Industry</h4>
                <p>{profile.industry || 'N/A'}</p>
            </div>
            <div className="data-group">
                <h4>Annual Revenue</h4>
                <p>{profile.key_financials?.revenue || 'N/A'}</p>
            </div>
            <div className="data-group">
                <h4>Total Employees</h4>
                <p>{profile.key_financials?.employees || 'N/A'}</p>
            </div>
            <div className="data-group full-width">
                <h4>Short Description</h4>
                <p>{profile.short_description || 'No description available.'}</p>
            </div>
        </div>
    );

    const renderLocations = () => {
        const hq = profile.headquarters_location;
        const sites = profile.production_sites || [];

        return (
            <div className="tab-content locations-grid">
                <div className="locations-summary">
                    <h4>Headquarters</h4>
                    <p>{hq?.city ? `${hq.city}, ${hq.country}` : 'N/A'}</p>
                    <p className="meta">{hq?.type || 'HQ'}</p>
                </div>

                <div className="sites-list">
                    <h4>Key Production Sites</h4>
                    {sites.length === 0 ? (
                        <p className="empty-msg">No major sites listed.</p>
                    ) : (
                        <ul className="site-cards">
                            {sites.map((site, i) => (
                                <li key={i} className="site-card">
                                    <div className="site-name">
                                        <strong>{site.city}</strong>, {site.country}
                                    </div>
                                    <div className="site-focus">{site.focus_area}</div>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            </div>
        );
    };

    const renderHistory = () => (
        <div className="tab-content history-stack">
            <div className="history-section">
                <h4>Founding & Background</h4>
                {profile.history?.founding_year && (
                    <p><strong>Founded:</strong> {profile.history.founding_year}</p>
                )}
                <p>{profile.history?.background || 'Background unavailable.'}</p>
            </div>
            <div className="history-section">
                <h4>Key Historical Milestones</h4>
                {profile.history?.key_milestones && profile.history.key_milestones.length > 0 ? (
                    <ul className="milestone-list">
                        {profile.history.key_milestones.map((ms, i) => (
                            <li key={i}>{ms}</li>
                        ))}
                    </ul>
                ) : (
                    <p className="empty-msg">No key milestones documented.</p>
                )}
            </div>
        </div>
    );

    const renderFinancial = () => (
        <div className="tab-content financial-grid">
            <div className="financial-card">
                <h4>Recent Revenue Trend</h4>
                <p>{profile.key_financials?.revenue_trend || 'N/A'}</p>
            </div>
            <div className="financial-card">
                <h4>Profitability (EBITDA margin)</h4>
                <p>{profile.key_financials?.profitability_trend || 'N/A'}</p>
            </div>
            <div className="financial-card full-width">
                <h4>General Market Position</h4>
                <p>{profile.competition_market_position || 'N/A'}</p>
            </div>
        </div>
    );

    const renderStrategy = () => (
        <div className="tab-content strategy-stack">
            <div className="strategy-section">
                <h4>Current Strategic Focus</h4>
                <p>{profile.strategic_direction?.focus || 'N/A'}</p>
            </div>
            <div className="strategy-section">
                <h4>Upcoming Major Investments</h4>
                {profile.strategic_direction?.investments && profile.strategic_direction.investments.length > 0 ? (
                    <ul className="investment-list">
                        {profile.strategic_direction.investments.map((inv, i) => (
                            <li key={i}>{inv}</li>
                        ))}
                    </ul>
                ) : (
                    <p className="empty-msg">No known major investments.</p>
                )}
            </div>
            <div className="strategy-section">
                <h4>Decarbonization / ESG Goals</h4>
                <p>{profile.strategic_direction?.decarbonization_goals || 'N/A'}</p>
            </div>
        </div>
    );

    return (
        <div className="profile-sections">
            <div className="tabs-header">
                {tabs.map(tab => (
                    <button
                        key={tab.id}
                        className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
                        onClick={() => setActiveTab(tab.id)}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>

            <div className="tab-body">
                {activeTab === 'basic' && renderBasicData()}
                {activeTab === 'locations' && renderLocations()}
                {activeTab === 'history' && renderHistory()}
                {activeTab === 'financial' && renderFinancial()}
                {activeTab === 'strategy' && renderStrategy()}
            </div>
        </div>
    );
};

export default ProfileSections;
