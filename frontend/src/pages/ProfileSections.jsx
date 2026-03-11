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
                <p>{profile?.basic_data?.name || 'N/A'}</p>
            </div>
            <div className="data-group">
                <h4>Headquarters</h4>
                <p>{profile?.basic_data?.hq_address || 'N/A'}</p>
            </div>
            <div className="data-group">
                <h4>Primary Industry</h4>
                <p>{profile?.basic_data?.company_focus || 'N/A'}</p>
            </div>
            <div className="data-group">
                <h4>Annual Revenue</h4>
                <p>{profile?.basic_data?.financials || 'N/A'}</p>
            </div>
            <div className="data-group">
                <h4>Total Employees</h4>
                <p>{profile?.basic_data?.fte || 'N/A'}</p>
            </div>
            <div className="data-group full-width">
                <h4>Recent Facts & Overview</h4>
                <p>{profile?.basic_data?.recent_facts || 'No description available.'}</p>
            </div>
        </div>
    );

    const renderLocations = () => {
        const sites = profile?.locations || [];

        return (
            <div className="tab-content locations-grid">
                <div className="sites-list full-width">
                    <h4 style={{ marginBottom: '1.5rem', borderBottom: '2px solid var(--border)', paddingBottom: '0.5rem' }}>Key Production Sites</h4>
                    {sites.length === 0 ? (
                        <p className="empty-msg">No major sites listed.</p>
                    ) : (
                        <div className="site-records-container" style={{
                            display: 'flex',
                            flexDirection: 'row',
                            flexWrap: 'nowrap',
                            overflowX: 'auto',
                            gap: '1.25rem',
                            paddingBottom: '1.25rem',
                            scrollbarWidth: 'thin',
                            scrollSnapType: 'x mandatory'
                        }}>
                            {sites.map((site, i) => (
                                <div key={i} className="site-record-card" style={{
                                    flex: '0 0 420px',
                                    padding: '1.25rem',
                                    border: '1px solid var(--border)',
                                    borderRadius: '12px',
                                    background: 'var(--bg-surface)',
                                    boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
                                    scrollSnapAlign: 'start',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    justifyContent: 'space-between'
                                }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
                                        <div>
                                            <h5 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--primary)', fontWeight: '700' }}>{site.city || 'Unknown Location'}</h5>
                                            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: '500' }}>{site.country || 'Unknown Country'}</span>
                                        </div>
                                        <div style={{ textAlign: 'right' }}>
                                            <div style={{ fontWeight: '700', color: 'var(--primary)', fontSize: '1rem' }}>{site.tons_per_year ? `${site.tons_per_year.toLocaleString()} t/y` : 'N/A capacity'}</div>
                                            <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Capacity</div>
                                        </div>
                                    </div>

                                    <div style={{ marginBottom: '1rem', background: 'var(--bg-secondary)', padding: '0.75rem', borderRadius: '8px' }}>
                                        <div style={{ fontSize: '0.7rem', fontWeight: '800', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '0.4rem', letterSpacing: '0.5px' }}>Main Products</div>
                                        <div style={{ fontSize: '0.9rem', color: 'var(--text-primary)', fontWeight: '500' }}>{site.final_products || 'General Steel Products'}</div>
                                    </div>

                                    {site.installed_base && site.installed_base.length > 0 && (
                                        <div style={{ borderTop: '1px solid var(--border)', paddingTop: '1rem' }}>
                                            <div style={{ fontSize: '0.7rem', fontWeight: '800', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '0.6rem', letterSpacing: '0.5px' }}>Installed Equipment</div>
                                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                                                {site.installed_base.map((eq, idx) => (
                                                    <span key={idx} style={{
                                                        background: 'var(--primary)',
                                                        color: 'white',
                                                        padding: '0.2rem 0.6rem',
                                                        borderRadius: '6px',
                                                        fontSize: '0.75rem',
                                                        fontWeight: '600',
                                                        boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
                                                    }}>
                                                        {eq.equipment_type}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        );
    };

    const renderHistory = () => (
        <div className="tab-content history-stack">
            <div className="history-section">
                <h4>SMS group Relationship</h4>
                <p><strong>Total Won Value:</strong> €{profile?.history?.total_won_value_eur || 'N/A'}</p>
                <p><strong>SMS Contact:</strong> {profile?.history?.sms_relationship || 'N/A'}</p>
                <p><strong>Customer Key Person:</strong> {profile?.history?.key_person || 'N/A'}</p>
            </div>
            <div className="history-section">
                <h4>Projects & Interactions</h4>
                <p><strong>Latest Projects:</strong> {profile?.history?.latest_projects || 'N/A'}</p>
                <p><strong>History:</strong> {profile?.basic_data?.ownership_history || 'N/A'}</p>
            </div>
        </div>
    );

    const renderFinancial = () => {
        const fh = profile?.financial_history || [];
        const latest = profile?.latest_balance_sheet || {};
        return (
            <div className="tab-content financial-grid">
                <div className="financial-card full-width">
                    <h4>Financial Health & Status</h4>
                    <p>{profile?.market_intelligence?.financial_health || 'N/A'}</p>
                </div>
                <div className="financial-card">
                    <h4>Latest Balance Sheet</h4>
                    <p><strong>Assets:</strong> {latest.assets || 'N/A'}</p>
                    <p><strong>Liabilities:</strong> {latest.liabilities || 'N/A'}</p>
                    <p><strong>Equity:</strong> {latest.equity || 'N/A'}</p>
                </div>
                {fh.length > 0 && (
                    <div className="financial-card full-width">
                        <h4>Historical Metrics</h4>
                        <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse', marginTop: '0.5rem' }}>
                            <thead>
                                <tr style={{ borderBottom: '2px solid var(--border)' }}>
                                    <th style={{ padding: '0.75rem 0.5rem' }}>Year</th>
                                    <th style={{ padding: '0.75rem 0.5rem' }}>Revenue (mEUR)</th>
                                    <th style={{ padding: '0.75rem 0.5rem' }}>EBITDA (mEUR)</th>
                                </tr>
                            </thead>
                            <tbody>
                                {fh.map((row, i) => (
                                    <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                                        <td style={{ padding: '0.6rem 0.5rem' }}>{row.year}</td>
                                        <td style={{ padding: '0.6rem 0.5rem' }}>{row.revenue_m_eur?.toLocaleString() || '—'}</td>
                                        <td style={{ padding: '0.6rem 0.5rem' }}>{row.ebitda_m_eur?.toLocaleString() || '—'}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        );
    };

    const renderStrategy = () => (
        <div className="tab-content strategy-stack">
            {profile?.priority_analysis?.company_explainer && (
                <div className="strategy-section explainer-section" style={{
                    background: 'var(--bg-secondary)',
                    padding: '1.5rem',
                    borderRadius: '8px',
                    borderLeft: '4px solid var(--primary)',
                    marginBottom: '2rem'
                }}>
                    <h4 style={{ marginTop: 0, color: 'var(--primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span>🎯</span> AI Ranking Deep Research Explainer
                    </h4>
                    <div className="explainer-text" style={{
                        lineHeight: '1.6',
                        fontSize: '0.95rem',
                        color: 'var(--text-primary)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '1rem'
                    }}>
                        {profile.priority_analysis.company_explainer.split('\n').filter(p => p.trim()).map((p, i) => (
                            <p key={i} style={{ margin: 0 }}>{p}</p>
                        ))}
                    </div>
                </div>
            )}

            <div className="strategy-section">
                <h4>Strategic Outlook & Market Position</h4>
                <p><strong>Market Position:</strong> {profile?.market_intelligence?.market_position || 'N/A'}</p>
                <p><strong>Outlook:</strong> {profile?.market_intelligence?.strategic_outlook || 'N/A'}</p>
            </div>
            <div className="strategy-section">
                <h4>Decarbonization / Tech Insights</h4>
                <p>{profile?.metallurgical_insights?.carbon_footprint_strategy || 'N/A'}</p>
                <p><strong>Modernization Potential:</strong> {profile?.metallurgical_insights?.modernization_potential || 'N/A'}</p>
            </div>
            <div className="strategy-section">
                <h4>Recommended SMS Sales Strategy</h4>
                <p><strong>Pitch:</strong> {profile?.sales_strategy?.value_proposition || 'N/A'}</p>
                <p><strong>Next Steps:</strong> {profile?.sales_strategy?.suggested_next_steps || 'N/A'}</p>
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
