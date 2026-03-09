import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../api/client';

const fetchNews = async ({ queryKey }) => {
    const [_key, companyName, equipmentType, country] = queryKey;
    // Build query params for global or company-specific news
    const params = new URLSearchParams();
    if (companyName && companyName !== 'All') params.set('company', companyName);
    if (equipmentType && equipmentType !== 'All') params.set('equipment_type', equipmentType);
    if (country && country !== 'All') params.set('country', country);
    const res = await api.get(`/data/news?${params.toString()}`);
    return res.data;
};

const NewsPanel = ({ companyName, equipmentType, country }) => {
    const { data, isLoading, isError } = useQuery({
        queryKey: ['news', companyName, equipmentType, country],
        queryFn: fetchNews,
        staleTime: 15 * 60 * 1000, // 15 minutes cache
        refetchOnWindowFocus: false,
    });

    if (isLoading) {
        return (
            <div style={{ padding: '1rem', textAlign: 'center', fontStyle: 'italic', color: 'var(--text-secondary)' }}>
                Gathering market intelligence...
            </div>
        );
    }

    if (isError) {
        return <div style={{ color: 'var(--danger)', padding: '1rem' }}>Failed to retrieve latest news.</div>;
    }

    const newsList = data?.news || [];

    if (newsList.length === 0) {
        return (
            <div style={{ padding: '1rem', color: 'var(--text-secondary)', textAlign: 'center' }}>
                <span style={{ fontSize: '2rem' }}>📰</span>
                <p>No recent news found. Check your API connection.</p>
            </div>
        );
    }

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem', marginTop: '0.5rem' }}>
            {newsList.map((item, idx) => (
                <div key={idx} style={{
                    paddingBottom: '0.85rem',
                    borderBottom: idx < newsList.length - 1 ? '1px solid var(--border)' : 'none'
                }}>
                    <a
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ fontWeight: '600', display: 'block', marginBottom: '0.3rem', color: 'var(--accent)', textDecoration: 'none', lineHeight: '1.3' }}
                    >
                        {item.title}
                    </a>
                    {item.source && (
                        <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', fontWeight: '500', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                            {item.source} &bull; {item.published_date ? new Date(item.published_date).toLocaleDateString() : ''}
                        </span>
                    )}
                    {item.description && (
                        <p style={{ fontSize: '0.83rem', color: 'var(--text-secondary)', marginTop: '0.25rem', lineHeight: '1.5' }}>
                            {item.description.length > 200 ? item.description.substring(0, 197) + '…' : item.description}
                        </p>
                    )}
                </div>
            ))}
        </div>
    );
};

export default NewsPanel;
