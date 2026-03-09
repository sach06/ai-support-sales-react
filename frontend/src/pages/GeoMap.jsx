import React from 'react';
import Plot from 'react-plotly.js';

const GeoMap = ({ data }) => {
    if (!data || data.length === 0) {
        return <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>No location data available for map.</div>;
    }

    // Filter plants that have valid lat/lon
    const mapData = data.filter(p => (p.latitude || p.map_latitude) && (p.longitude || p.map_longitude));

    if (mapData.length === 0) {
        return <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>No coordinates available for the selected plants.</div>;
    }

    const hoverText = mapData.map(p => {
        const capacity = p.capacity || p.capacity_internal || p['Nominal Capacity'] || 'N/A';
        const site = p.City || p.site_name || 'N/A';
        const equip = p.equipment_list ? p.equipment_list.join(', ') : (p.equipment_type || 'N/A');

        return `<b>${p.name || p.company_name || 'Unknown Company'}</b><br>` +
            `Equipment: ${equip}<br>` +
            `Site: ${site}<br>` +
            `Capacity: ${capacity}`;
    });

    // Map colors based on operational status
    const colors = mapData.map(p => {
        const status = String(p.status_internal || p['Status of the Plant'] || '').toLowerCase();

        // Operational: Green
        if (status.includes('operating') || status.includes('operational') || status.includes('active') || status.includes('running')) {
            return '#2f855a'; // Deep green
        }

        // Projects/Future: Orange
        if (status.includes('project') || status.includes('construction') || status.includes('planned') || status.includes('upcoming')) {
            return '#dd6b20'; // Warm orange
        }

        // Off/Shut down: Red
        if (status.includes('shut down') || status.includes('idle') || status.includes('abandoned') || status.includes('inactive')) {
            return '#c53030'; // Balanced red
        }

        return '#718096'; // Gray fallback
    });

    return (
        <Plot
            data={[
                {
                    type: 'scattermapbox',
                    lat: mapData.map(p => p.map_latitude || p.latitude),
                    lon: mapData.map(p => p.map_longitude || p.longitude),
                    mode: 'markers',
                    marker: {
                        size: 9,
                        color: colors,
                        opacity: 0.8
                    },
                    text: hoverText,
                    hoverinfo: 'text'
                }
            ]}
            layout={{
                autosize: true,
                margin: { l: 0, r: 0, t: 0, b: 0 },
                mapbox: {
                    style: 'carto-positron',
                    center: {
                        lat: mapData.length > 0 ? mapData.reduce((sum, p) => sum + parseFloat(p.map_latitude || p.latitude), 0) / mapData.length : 48,
                        lon: mapData.length > 0 ? mapData.reduce((sum, p) => sum + parseFloat(p.map_longitude || p.longitude), 0) / mapData.length : 10
                    },
                    zoom: 2
                },
                showlegend: false,
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent'
            }}
            useResizeHandler={true}
            style={{ width: '100%', height: '100%' }}
        />
    );
};

export default GeoMap;
