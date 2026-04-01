import React, { useMemo } from 'react';

// ── Mini box-plot drawn in SVG ─────────────────────────────────────────────
const BoxPlot = ({ data, label, unit = '', color = '#6c63ff' }) => {
    if (!data || !data.q1) return null;
    const { min, max, q1, q3, median } = data;
    const range = max - min || 1;
    const pct = (v) => ((v - min) / range) * 100;

    return (
        <div className="boxplot-wrap">
            <div className="boxplot-label">{label}</div>
            <svg viewBox="0 0 200 40" className="boxplot-svg">
                {/* whiskers */}
                <line x1={pct(min) * 2} y1={20} x2={pct(q1) * 2} y2={20}
                    stroke={color} strokeWidth="1.5" strokeDasharray="3,2" />
                <line x1={pct(q3) * 2} y1={20} x2={pct(max) * 2} y2={20}
                    stroke={color} strokeWidth="1.5" strokeDasharray="3,2" />
                {/* caps */}
                <line x1={pct(min) * 2} y1={12} x2={pct(min) * 2} y2={28}
                    stroke={color} strokeWidth="2" />
                <line x1={pct(max) * 2} y1={12} x2={pct(max) * 2} y2={28}
                    stroke={color} strokeWidth="2" />
                {/* IQR box */}
                <rect x={pct(q1) * 2} y={10} width={(pct(q3) - pct(q1)) * 2} height={20}
                    fill={color} fillOpacity="0.15" stroke={color} strokeWidth="1.5" rx="2" />
                {/* median line */}
                <line x1={pct(median) * 2} y1={10} x2={pct(median) * 2} y2={30}
                    stroke={color} strokeWidth="2.5" />
            </svg>
            <div className="boxplot-stats">
                <span>Min: <b>{min}{unit}</b></span>
                <span>Median: <b>{median}{unit}</b></span>
                <span>Max: <b>{max}{unit}</b></span>
            </div>
        </div>
    );
};

// ── Mini histogram / bell curve ───────────────────────────────────────────
const Histogram = ({ values, label, unit = '', color = '#6c63ff', bins = 20 }) => {
    const stats = useMemo(() => {
        if (!values || values.length === 0) return null;
        const min = Math.min(...values);
        const max = Math.max(...values);
        const avg = values.reduce((a, b) => a + b, 0) / values.length;
        return { min, max, avg };
    }, [values]);

    const hist = useMemo(() => {
        if (!values || values.length === 0) return [];
        const min = Math.min(...values);
        const max = Math.max(...values);
        const range = max - min || 1;
        const binSize = range / bins;
        const counts = Array(bins).fill(0);
        values.forEach(v => {
            const idx = Math.min(Math.floor((v - min) / binSize), bins - 1);
            counts[idx]++;
        });
        const maxCount = Math.max(...counts, 1);
        return counts.map((c, i) => ({
            x: i,
            height: (c / maxCount) * 100,
            count: c,
            label: `${(min + i * binSize).toFixed(0)}–${(min + (i + 1) * binSize).toFixed(0)}${unit}`,
        }));
    }, [values, bins, unit]);

    if (!hist.length || !stats) return null;
    const barW = 200 / bins;

    return (
        <div className="histogram-wrap">
            <div className="boxplot-label">{label}</div>
            <svg viewBox={`0 0 200 85`} className="histogram-svg">
                {hist.map((bar, i) => (
                    <rect key={i}
                        x={i * barW + 0.5} y={70 - bar.height * 0.65}
                        width={barW - 1} height={bar.height * 0.65}
                        fill={color} fillOpacity="0.75" rx="1"
                    >
                        <title>{bar.label}: {bar.count}</title>
                    </rect>
                ))}

                {/* X Axis labels */}
                <line x1="0" y1="70" x2="200" y2="70" stroke="#cbd5e0" strokeWidth="1" />

                <text x="2" y="82" fontSize="7" fill="#718096" textAnchor="start">Min: {stats.min.toFixed(0)}{unit}</text>
                <text x="100" y="82" fontSize="7" fill="#718096" textAnchor="middle">Avg: {stats.avg.toFixed(0)}{unit}</text>
                <text x="198" y="82" fontSize="7" fill="#718096" textAnchor="end">Max: {stats.max.toFixed(0)}{unit}</text>
            </svg>
        </div>
    );
};

// ── Status → fixed colour mapping (green = operating, red = shut down) ────
const STATUS_COLOR_MAP = {
    'operating': '#22c55e',
    'operational': '#22c55e',
    'active': '#22c55e',
    'shut down': '#ef4444',
    'shutdown': '#ef4444',
    'abandoned': '#ef4444',
    'demolished': '#ef4444',
    'idle': '#f59e0b',
    'standby': '#f59e0b',
    'mothballed': '#f59e0b',
    'commissioning': '#3b82f6',
    'ramp-up': '#3b82f6',
    'planned': '#a78bfa',
    'unknown': '#6b7280',
};

const getStatusColor = (label, fallbackIndex, fallbackPalette) => {
    const key = String(label || '').toLowerCase().trim();
    for (const [k, v] of Object.entries(STATUS_COLOR_MAP)) {
        if (key.includes(k)) return v;
    }
    return fallbackPalette[fallbackIndex % fallbackPalette.length];
};

// ── Donut chart for categorical data ─────────────────────────────────────
const FALLBACK_PALETTE = ['#22c55e', '#f59e0b', '#ef4444', '#6b7280', '#a78bfa'];

const DonutChart = ({ data, title, palette, useStatusColors = false }) => {
    const entries = Object.entries(data || {}).sort((a, b) => b[1] - a[1]);
    const total = entries.reduce((s, [, v]) => s + v, 0);
    if (!total) return null;

    const slices = entries
        .reduce((acc, [label, value], i) => {
            const angle = (value / total) * 2 * Math.PI;
            const start = acc.cumAngle;
            const end = start + angle;
            const x1 = 50 + 40 * Math.cos(start);
            const y1 = 50 + 40 * Math.sin(start);
            const x2 = 50 + 40 * Math.cos(end);
            const y2 = 50 + 40 * Math.sin(end);
            const large = angle > Math.PI ? 1 : 0;
            const resolvedPalette = palette || FALLBACK_PALETTE;
            const color = useStatusColors
                ? getStatusColor(label, i, resolvedPalette)
                : resolvedPalette[i % resolvedPalette.length];

            acc.slices.push({ label, value, color, x1, y1, x2, y2, large });
            acc.cumAngle = end;
            return acc;
        }, { cumAngle: -Math.PI / 2, slices: [] })
        .slices;

    return (
        <div className="donut-wrap">
            <div className="boxplot-label">{title}</div>
            <div className="donut-inner">
                <svg viewBox="0 0 100 100" className="donut-svg">
                    {slices.map((s, i) => (
                        <path key={i}
                            d={`M50,50 L${s.x1},${s.y1} A40,40 0 ${s.large},1 ${s.x2},${s.y2} Z`}
                            fill={s.color} stroke="var(--bg-primary)" strokeWidth="1.5"
                        >
                            <title>{s.label}: {s.value} ({((s.value / total) * 100).toFixed(1)}%)</title>
                        </path>
                    ))}
                    <circle cx="50" cy="50" r="23" fill="var(--bg-surface)" />
                    <text x="50" y="54" textAnchor="middle" fontSize="9" fill="var(--text-primary)" fontWeight="600">
                        {total}
                    </text>
                    <text x="50" y="63" textAnchor="middle" fontSize="6" fill="var(--text-secondary)">
                        plants
                    </text>
                </svg>
                <div className="donut-legend">
                    {slices.slice(0, 6).map((s, i) => (
                        <div key={i} className="legend-item">
                            <span className="legend-dot" style={{ background: s.color }} />
                            <span className="legend-label">{s.label}</span>
                            <span className="legend-value">{((s.value / total) * 100).toFixed(0)}%</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

// ── Main Statistics Panel ─────────────────────────────────────────────────
const EQUIP_PALETTE = ['#6c63ff', '#06b6d4', '#f59e0b', '#ec4899', '#22c55e',
    '#f97316', '#8b5cf6', '#14b8a6', '#facc15', '#64748b'];

const StatisticsPanel = ({ summary, displayTotal }) => {
    if (!summary || !summary.total) {
        return (
            <div className="stats-empty">
                <p>No data available for statistics.</p>
            </div>
        );
    }

    const { total, status_counts = {}, equipment_counts = {}, capacity = {}, age = {}, start_year = {} } = summary;
    const finalTotal = displayTotal !== undefined ? displayTotal : total;

    return (
        <div className="stats-panel">
            <p className="stats-desc">
                Distribution analysis of <b>{finalTotal.toLocaleString()}</b> installed plant records —
                capacities, ages, operational status and equipment mix.
            </p>

            {/* Row 1: donuts */}
            <div className="stats-row-2">
                <DonutChart data={status_counts} title="Operational Status" useStatusColors={true} />
                <DonutChart data={equipment_counts} title="Top Equipment Types" palette={EQUIP_PALETTE} />
            </div>

            {/* Row 2: histograms */}
            <div className="stats-row-3">
                <Histogram values={capacity.values} label="Nominal Capacity Distribution" unit=" kt/y" color="#6c63ff" />
                <Histogram values={age.values} label="Equipment Age Distribution" unit=" yrs" color="#06b6d4" />
                <Histogram values={start_year.values} label="Year of Startup Distribution" unit="" color="#f59e0b" />
            </div>

            {/* Row 3: box plots */}
            <div className="stats-row-boxplots">
                <BoxPlot data={capacity} label="Capacity (kt/y)" unit=" kt/y" color="#6c63ff" />
                <BoxPlot data={age} label="Equipment Age (years)" unit=" yrs" color="#06b6d4" />
                <BoxPlot data={start_year} label="Startup Year" unit="" color="#f59e0b" />
            </div>
        </div>
    );
};

export default StatisticsPanel;
