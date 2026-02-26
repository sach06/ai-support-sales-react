import React from 'react';
import Plot from 'react-plotly.js';

const GeoMap = ({ data }) => {
    if (!data || data.length === 0) {
        return <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>No location data available for map.</div>;
    }

    // Filter plants that have valid lat/lon
    const mapData = data.filter(p => p.latitude && p.longitude);

    if (mapData.length === 0) {
        return <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>No coordinates available for the selected plants.</div>;
    }

    const hoverText = mapData.map(p =>
        `${p.company_name}<br>` +
        `Site: ${p.site_name || 'N/A'}<br>` +
        `Equipment: ${p.equipment_type || 'N/A'}<br>` +
        `Quality: ${p.match_type || 'N/A'}`
    );

    // Map colors to match python app
    const colors = mapData.map(p => {
        const type = p.match_type;
        if (type === 'Excellent') return '#007020';
        if (type === 'Good') return '#38a169';
        if (type === 'Okay') return '#d69e2e';
        return '#e53e3e';
    });

    return (
        <Plot
            data={[
                {
                    type: 'scattermapbox',
                    lat: mapData.map(p => p.latitude),
                    lon: mapData.map(p => p.longitude),
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
                        lat: mapData.length > 0 ? mapData.reduce((sum, p) => sum + parseFloat(p.latitude), 0) / mapData.length : 48,
                        lon: mapData.length > 0 ? mapData.reduce((sum, p) => sum + parseFloat(p.longitude), 0) / mapData.length : 10
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
