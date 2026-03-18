import React, { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import Plot from 'react-plotly.js';
import { getCompanyIntelligence } from '../api/rankingApi';

const RankingCharts = ({ data, selectedCompany }) => {
    if (!data || data.length === 0) return null;

    const oppTypes = useMemo(() => {
        const types = data.reduce((acc, row) => {
            const t = row.opportunity_type || 'Unknown';
            acc[t] = (acc[t] || 0) + 1;
            return acc;
        }, {});

        return {
            labels: Object.keys(types),
            values: Object.values(types)
        };
    }, [data]);

    const { data: companyIntel } = useQuery({
        queryKey: ['company_intelligence', selectedCompany?.company, selectedCompany?.equipment_type, selectedCompany?.country],
        queryFn: () => getCompanyIntelligence({
            companyName: selectedCompany?.company,
            equipmentType: selectedCompany?.equipment_type,
            country: selectedCompany?.country,
        }),
        enabled: Boolean(selectedCompany?.company),
        staleTime: 120_000,
    });

    const wonLost = companyIntel?.won_vs_lost || {
        won_count: 0,
        lost_count: 0,
        win_rate_pct: 0,
        won_value_eur: 0,
    };

    const orderIntake = Array.isArray(companyIntel?.order_intake_history)
        ? companyIntel.order_intake_history
        : [];

    const competitorDeepDive = Array.isArray(companyIntel?.competitor_deep_dive)
        ? companyIntel.competitor_deep_dive
        : [];

    const commonLayout = {
        margin: { t: 30, b: 40, l: 40, r: 20 },
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        font: { color: '#718096' },
        showlegend: false
    };

    return (
        <div className="ranking-charts-container">
            <div className="chart-wrapper">
                <h4>Opportunity Type Breakdown</h4>
                <Plot
                    data={[
                        {
                            labels: oppTypes.labels,
                            values: oppTypes.values,
                            type: 'pie',
                            hole: 0.4,
                            marker: {
                                colors: ['#1f4788', '#00a4e4', '#e2e8f0', '#38a169', '#d69e2e']
                            }
                        }
                    ]}
                    layout={{
                        ...commonLayout,
                        showlegend: true,
                        legend: { orientation: 'h', y: -0.2 }
                    }}
                    useResizeHandler={true}
                    style={{ width: '100%', height: '300px' }}
                />
            </div>

            <div className="chart-wrapper">
                <h4>Won vs Lost Projects ({selectedCompany?.company || 'Selected Customer'})</h4>
                <Plot
                    data={[
                        {
                            x: ['Won', 'Lost / Not Won'],
                            y: [wonLost.won_count || 0, wonLost.lost_count || 0],
                            type: 'bar',
                            marker: { color: ['#2f855a', '#c05621'] },
                            text: [
                                `${wonLost.won_count || 0}`,
                                `${wonLost.lost_count || 0}`,
                            ],
                            textposition: 'auto',
                        }
                    ]}
                    layout={{
                        ...commonLayout,
                        yaxis: { title: 'Project Count' }
                    }}
                    useResizeHandler={true}
                    style={{ width: '100%', height: '250px' }}
                />
                <div className="intel-kpi-strip">
                    <span><strong>Win Rate:</strong> {(wonLost.win_rate_pct || 0).toFixed(1)}%</span>
                    <span><strong>Won Value:</strong> EUR {(wonLost.won_value_eur || 0).toLocaleString()}</span>
                </div>
            </div>

            <div className="chart-wrapper chart-full-width">
                <h4>Order Intake History (EUR)</h4>
                <Plot
                    data={[
                        {
                            x: orderIntake.map((row) => row.Year),
                            y: orderIntake.map((row) => row['Total Value (EUR)'] || 0),
                            type: 'bar',
                            marker: { color: '#1f4788' },
                            text: orderIntake.map((row) => `EUR ${(row['Total Value (EUR)'] || 0).toLocaleString()}`),
                            textposition: 'outside',
                        }
                    ]}
                    layout={{
                        ...commonLayout,
                        xaxis: { title: 'Year' },
                        yaxis: { title: 'Amount (EUR)' },
                    }}
                    useResizeHandler={true}
                    style={{ width: '100%', height: '300px' }}
                />
            </div>

            <div className="chart-wrapper chart-full-width">
                <h4>Competitor Deep Dive For {selectedCompany?.company || 'Selected Customer'}</h4>
                {companyIntel?.deep_dive_summary && (
                    <p className="deep-dive-summary">{companyIntel.deep_dive_summary}</p>
                )}
                <div className="competitor-grid">
                    {competitorDeepDive.map((item) => (
                        <div className="competitor-card" key={item.competitor}>
                            <h5>{item.competitor}</h5>
                            <p><strong>Positioning:</strong> {item.positioning}</p>
                            <p><strong>Threat:</strong> {item.threat_on_selected_scope}</p>
                            <p><strong>SMS Counter-Strategy:</strong> {item.sms_counter_strategy}</p>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default RankingCharts;
