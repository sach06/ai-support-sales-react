import React, { useState } from 'react';
import Plot from 'react-plotly.js';

const ProfileSections = ({ profile }) => {
    const [activeTab, setActiveTab] = useState('basic');

    if (!profile) return null;

    const asArray = (value) => (Array.isArray(value) ? value : []);
    const asObject = (value) => (value && typeof value === 'object' && !Array.isArray(value) ? value : {});
    const asText = (value) => {
        if (typeof value === 'string') return value;
        if (value == null) return '';
        if (typeof value === 'object') {
            // Handle nested objects by converting to readable format
            if (Array.isArray(value)) return value.map(v => String(v)).join(', ');
            return Object.entries(value)
                .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : String(v)}`)
                .join(' | ');
        }
        return String(value);
    };

    const renderText = (value, fallback = 'N/A') => {
        const text = asText(value).trim();
        return text || fallback;
    };

    const tabs = [
        { id: 'basic', label: 'Basic Data' },
        { id: 'locations', label: 'Locations & Setup' },
        { id: 'history', label: 'Background & History' },
        { id: 'financial', label: 'Financial Status' },
        { id: 'strategy', label: 'Customer Strategy' },
        { id: 'evidence', label: 'Internal Evidence' },
        ...(profile?.modular_sections ? [{ id: 'modular', label: 'Deep-Dive Modules' }] : []),
    ];

    const renderBasicData = () => (
        <div className="tab-content basic-data-grid">
            <div className="data-group">
                <h4>Legal Name</h4>
                <p>{renderText(profile?.basic_data?.name)}</p>
            </div>
            <div className="data-group">
                <h4>Headquarters</h4>
                <p>{renderText(profile?.basic_data?.hq_address)}</p>
            </div>
            <div className="data-group">
                <h4>Primary Industry</h4>
                <p>{renderText(profile?.basic_data?.company_focus)}</p>
            </div>
            <div className="data-group">
                <h4>Annual Revenue</h4>
                <p>{renderText(profile?.basic_data?.financials)}</p>
            </div>
            <div className="data-group">
                <h4>Total Employees</h4>
                <p>{renderText(profile?.basic_data?.fte)}</p>
            </div>
            <div className="data-group">
                <h4>Ownership Type</h4>
                <p>{renderText(profile?.basic_data?.ownership_type ?? profile?.basic_data?.owner)}</p>
            </div>
            <div className="data-group full-width">
                <h4>Board And Management Deep Dive</h4>
                <p>{renderText(profile?.basic_data?.management_deep_dive ?? profile?.basic_data?.management)}</p>
            </div>
            <div className="data-group full-width">
                <h4>Decision Dynamics</h4>
                <p>{renderText(profile?.basic_data?.decision_governance)}</p>
            </div>
            <div className="data-group full-width">
                <h4>Recent Facts & Overview</h4>
                <p>{renderText(profile?.basic_data?.recent_facts, 'No description available.')}</p>
            </div>
        </div>
    );

    const renderLocations = () => {
        const sites = asArray(profile?.locations);

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
                                            {(() => {
                                                const NA_VALS = ['not available', 'n/a', 'na', 'unknown', 'none', ''];
                                                const rawCity = String(site.city || '').trim();
                                                const rawCountry = String(site.country || '').trim();
                                                const cityIsBlank = NA_VALS.includes(rawCity.toLowerCase());
                                                // Best city label: city → plant_type (from address or location) → "Plant site, Country"
                                                const cityLabel = cityIsBlank
                                                    ? (site.plant_type && !NA_VALS.includes(String(site.plant_type).toLowerCase())
                                                        ? site.plant_type
                                                        : rawCountry
                                                            ? `Plant site — ${rawCountry}`
                                                            : 'Plant site')
                                                    : rawCity;
                                                const countryLabel = NA_VALS.includes(rawCountry.toLowerCase()) ? '' : rawCountry;
                                                return (
                                                    <>
                                                        <h5 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--primary)', fontWeight: '700' }}>{cityLabel}</h5>
                                                        {countryLabel && <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: '500' }}>{countryLabel}</span>}
                                                    </>
                                                );
                                            })()}
                                        </div>
                                        <div style={{ textAlign: 'right' }}>
                                            {(() => {
                                                const capRaw = String(site.tons_per_year || '').trim();
                                                const NA_VALS = ['not available', 'n/a', 'na', 'none', '', 'null'];
                                                const capLabel = NA_VALS.includes(capRaw.toLowerCase()) ? null : capRaw;
                                                return capLabel
                                                    ? <><div style={{ fontWeight: '700', color: 'var(--primary)', fontSize: '1rem' }}>{capLabel} t/y</div><div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Capacity</div></>
                                                    : <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Capacity unknown</div>;
                                            })()}
                                        </div>
                                    </div>

                                    <div style={{ marginBottom: '1rem', background: 'var(--bg-secondary)', padding: '0.75rem', borderRadius: '8px' }}>
                                        <div style={{ fontSize: '0.7rem', fontWeight: '800', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '0.4rem', letterSpacing: '0.5px' }}>Main Products</div>
                                        {(() => {
                                            const NA_VALS = ['not available', 'n/a', 'na', 'none', '', 'null'];
                                            const prod = String(site.final_products || '').trim();
                                            return <div style={{ fontSize: '0.9rem', color: 'var(--text-primary)', fontWeight: '500' }}>{NA_VALS.includes(prod.toLowerCase()) ? 'General Steel Products' : prod}</div>;
                                        })()}
                                    </div>

                                    {asArray(site.installed_base).length > 0 && (
                                        <div style={{ borderTop: '1px solid var(--border)', paddingTop: '1rem' }}>
                                            <div style={{ fontSize: '0.7rem', fontWeight: '800', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '0.6rem', letterSpacing: '0.5px' }}>Installed Equipment</div>
                                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                                                {asArray(site.installed_base).map((eq, idx) => (
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
            <div className="history-section">
                <h4>Active Opportunity Deep Dive</h4>
                <p>{profile?.history?.active_opportunity_deep_dive || 'No active opportunity deep dive available yet.'}</p>
            </div>
            {Array.isArray(profile?.order_intake_history) && profile.order_intake_history.length > 0 && (
                <div className="history-section">
                    <h4>Order Intake History (EUR)</h4>
                    <Plot
                        data={[
                            {
                                x: profile.order_intake_history.map((row) => row.year),
                                y: profile.order_intake_history.map((row) => row.amount_eur || 0),
                                type: 'bar',
                                marker: { color: '#1f4788' },
                            }
                        ]}
                        layout={{
                            margin: { t: 10, b: 40, l: 60, r: 20 },
                            paper_bgcolor: 'transparent',
                            plot_bgcolor: 'transparent',
                            xaxis: { title: 'Year' },
                            yaxis: { title: 'Amount (EUR)' },
                        }}
                        useResizeHandler={true}
                        style={{ width: '100%', height: '260px' }}
                    />
                    <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse', marginTop: '0.5rem' }}>
                        <thead>
                            <tr style={{ borderBottom: '2px solid var(--border)' }}>
                                <th style={{ padding: '0.75rem 0.5rem' }}>Year</th>
                                <th style={{ padding: '0.75rem 0.5rem' }}>Amount (EUR)</th>
                                <th style={{ padding: '0.75rem 0.5rem' }}>Won Value (EUR)</th>
                                <th style={{ padding: '0.75rem 0.5rem' }}>Win Rate %</th>
                            </tr>
                        </thead>
                        <tbody>
                            {profile.order_intake_history.map((row, i) => (
                                <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                                    <td style={{ padding: '0.6rem 0.5rem' }}>{row.year}</td>
                                    <td style={{ padding: '0.6rem 0.5rem' }}>{(row.amount_eur || 0).toLocaleString()}</td>
                                    <td style={{ padding: '0.6rem 0.5rem' }}>{(row.won_value_eur || 0).toLocaleString()}</td>
                                    <td style={{ padding: '0.6rem 0.5rem' }}>{(row.win_rate_pct || 0).toFixed(1)}%</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );

    const renderFinancial = () => {
        const fh = asArray(profile?.financial_history);
        const latest = asObject(profile?.latest_balance_sheet);
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
                    <h4 style={{ marginTop: 0, color: 'var(--primary)' }}>
                        Priority Ranking Assessment
                    </h4>
                    <div className="explainer-text" style={{
                        lineHeight: '1.6',
                        fontSize: '0.95rem',
                        color: 'var(--text-primary)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '1rem'
                    }}>
                        {asText(profile?.priority_analysis?.company_explainer).split('\n').filter(p => p.trim()).map((p, i) => (
                            <p key={i} style={{ margin: 0 }}>{p}</p>
                        ))}
                    </div>
                </div>
            )}

            <div className="strategy-section">
                <h4>Strategic Outlook & Market Position</h4>
                <p><strong>Market Position:</strong> {renderText(profile?.market_intelligence?.market_position)}</p>
                <p><strong>Outlook:</strong> {renderText(profile?.market_intelligence?.strategic_outlook)}</p>
            </div>
            <div className="strategy-section">
                <h4>SMS Group Relationship And Leverage Points</h4>
                <p><strong>Relationship Assessment:</strong> {renderText(profile?.history?.sms_relationship ?? profile?.sales_strategy?.sms_relationship_assessment)}</p>
                <p><strong>SMS Strengths To Leverage:</strong> {renderText(profile?.sales_strategy?.sms_strengths_to_leverage)}</p>
            </div>
            <div className="strategy-section">
                <h4>Decarbonization / Tech Insights</h4>
                <p>{renderText(profile?.metallurgical_insights?.carbon_footprint_strategy)}</p>
                <p><strong>Modernization Potential:</strong> {renderText(profile?.metallurgical_insights?.modernization_potential)}</p>
            </div>
            <div className="strategy-section">
                <h4>Recommended SMS Sales Strategy</h4>
                <p><strong>Pitch:</strong> {renderText(profile?.sales_strategy?.value_proposition)}</p>
                <p><strong>Next Steps:</strong> {renderText(profile?.sales_strategy?.suggested_next_steps)}</p>
            </div>
        </div>
    );

    const renderEvidence = () => {
        const evidence = asArray(profile?.internal_knowledge_evidence);
        const signals = asObject(profile?.internal_knowledge_signals);
        const referencesRaw = profile?.references;
        const references = Array.isArray(referencesRaw)
            ? referencesRaw
            : asText(referencesRaw).trim()
                ? [asText(referencesRaw)]
                : [];
        const rankedSignals = Object.entries(signals)
            .filter(([key]) => key.endsWith('_signal'))
            .sort((a, b) => b[1] - a[1]);

        return (
            <div className="tab-content evidence-stack">
                <div className="strategy-section">
                    <h4>Evidence Signals</h4>
                    <div className="evidence-signal-grid">
                        <div className="evidence-signal-card">
                            <span className="signal-label">Matched documents</span>
                            <strong>{Math.round(signals.knowledge_doc_count || 0)}</strong>
                        </div>
                        <div className="evidence-signal-card">
                            <span className="signal-label">Best match score</span>
                            <strong>{Math.round(signals.knowledge_best_match_score || 0)}</strong>
                        </div>
                        <div className="evidence-signal-card">
                            <span className="signal-label">Average match score</span>
                            <strong>{(signals.knowledge_avg_match_score || 0).toFixed(1)}</strong>
                        </div>
                    </div>
                    {rankedSignals.length > 0 && (
                        <div className="signal-bars">
                            {rankedSignals.map(([key, value]) => (
                                <div className="signal-row" key={key}>
                                    <span className="signal-name">{key.replace('knowledge_', '').replace('_signal', '')}</span>
                                    <div className="signal-bar-track">
                                        <div className="signal-bar-fill" style={{ width: `${Math.round((value || 0) * 100)}%` }} />
                                    </div>
                                    <span className="signal-value">{Math.round((value || 0) * 100)}%</span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                <div className="strategy-section">
                    <h4>Matched Internal Documents</h4>
                    {evidence.length === 0 ? (
                        <p className="empty-msg">No internal evidence has been matched for this profile yet.</p>
                    ) : (
                        <div className="evidence-card-list">
                            {evidence.map((item, index) => (
                                <article className="evidence-card" key={`${item.source_name}-${index}`}>
                                    <div className="evidence-card-header">
                                        <div>
                                            <h5>{item.source_name}</h5>
                                            <p className="evidence-folder">{item.folder}</p>
                                        </div>
                                        <span className="evidence-score">Match {item.score}</span>
                                    </div>
                                    {asArray(item.topics).length > 0 && (
                                        <div className="evidence-topics">
                                            {asArray(item.topics).map((topic) => (
                                                <span className="evidence-topic" key={topic}>{topic}</span>
                                            ))}
                                        </div>
                                    )}
                                    <p className="evidence-snippet">{item.snippet}</p>
                                </article>
                            ))}
                        </div>
                    )}
                </div>

                <div className="strategy-section">
                    <h4>Reference Trail</h4>
                    {references.length === 0 ? (
                        <p className="empty-msg">No source references are attached to this profile.</p>
                    ) : (
                        <div className="reference-list">
                            {references.map((reference, index) => (
                                <div className="reference-item" key={`${reference}-${index}`}>{reference}</div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        );
    };

    const renderModular = () => {
        const modSections = profile?.modular_sections || {};
        
        return (
            <div className="tab-content modular-stack">
                {Object.entries(modSections).length === 0 ? (
                    <p className="empty-msg">No modular sections available.</p>
                ) : (
                    Object.entries(modSections).map(([moduleKey, moduleContent]) => (
                        <div key={moduleKey} className="modular-module">
                            <div className="module-header">
                                <h4>{moduleKey.replace('module_', 'Module ').toUpperCase()}</h4>
                            </div>
                            {typeof moduleContent === 'object' && moduleContent !== null ? (
                                <div className="module-content">
                                    {Object.entries(moduleContent).map(([key, value]) => (
                                        <div key={key} className="module-field">
                                            <h5 style={{ margin: '1rem 0 0.5rem 0', fontSize: '0.95rem', fontWeight: '600', color: 'var(--primary)' }}>
                                                {key.replace(/_/g, ' ').split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
                                            </h5>
                                            <div style={{ fontSize: '0.9rem', lineHeight: '1.6', color: 'var(--text-primary)' }}>
                                                {Array.isArray(value) ? (
                                                    value.map((item, idx) => (
                                                        <div key={idx} style={{ marginBottom: '0.5rem' }}>
                                                            {typeof item === 'object' 
                                                                ? JSON.stringify(item, null, 2) 
                                                                : asText(item)}
                                                        </div>
                                                    ))
                                                ) : (
                                                    asText(value)
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p style={{ marginTop: '1rem', color: 'var(--text-primary)' }}>{asText(moduleContent)}</p>
                            )}
                        </div>
                    ))
                )}
            </div>
        );
    };

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
                {activeTab === 'evidence' && renderEvidence()}
                {activeTab === 'modular' && renderModular()}
            </div>
        </div>
    );
};

export default ProfileSections;
