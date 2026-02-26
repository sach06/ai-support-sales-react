import React, { useMemo } from 'react';
import Plot from 'react-plotly.js';

const RankingCharts = ({ data }) => {
    if (!data || data.length === 0) return null;

    // 1. Score Distribution (Histogram)
    const scores = data.map(d => Math.min(100, Math.max(0, d.score * 100)));

    // 2. Top Countries by Average Score (Bar Chart)
    const countryStats = useMemo(() => {
        const stats = data.reduce((acc, row) => {
            const country = row.country || 'Unknown';
            if (!acc[country]) {
                acc[country] = { count: 0, totalScore: 0 };
            }
            acc[country].count += 1;
            acc[country].totalScore += (row.score * 100);
            return acc;
        }, {});

        // Calculate averages and sort
        const result = Object.entries(stats)
            .map(([country, values]) => ({
                country,
                avgScore: values.totalScore / values.count,
                count: values.count
            }))
            .sort((a, b) => b.avgScore - a.avgScore)
            .slice(0, 10); // Top 10

        return result;
    }, [data]);

    // 3. Opportunity Types (Pie Chart)
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
                <h4>Score Distribution</h4>
                <Plot
                    data={[
                        {
                            x: scores,
                            type: 'histogram',
                            marker: { color: '#1f4788' },
                            xbins: { start: 0, end: 100, size: 5 }
                        }
                    ]}
                    layout={{
                        ...commonLayout,
                        xaxis: { title: 'Priority Score (0-100)', range: [0, 100] },
                        yaxis: { title: 'Number of Customers' }
                    }}
                    useResizeHandler={true}
                    style={{ width: '100%', height: '250px' }}
                />
            </div>

            <div className="chart-wrapper">
                <h4>Top Countries by Avg Score (Top 10)</h4>
                <Plot
                    data={[
                        {
                            x: countryStats.map(c => c.country),
                            y: countryStats.map(c => c.avgScore),
                            type: 'bar',
                            marker: { color: '#00a4e4' },
                            text: countryStats.map(c => `${c.avgScore.toFixed(1)} (n=${c.count})`),
                            textposition: 'auto',
                        }
                    ]}
                    layout={{
                        ...commonLayout,
                        yaxis: { title: 'Avg Score', range: [0, 100] }
                    }}
                    useResizeHandler={true}
                    style={{ width: '100%', height: '250px' }}
                />
            </div>

            <div className="chart-wrapper chart-full-width">
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
        </div>
    );
};

export default RankingCharts;
