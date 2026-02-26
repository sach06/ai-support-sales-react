import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../../api/client';

const fetchNews = async ({ queryKey }) => {
    const [_key, companyName] = queryKey;
    if (companyName === 'All') return { news: [] };
    const res = await api.get(`/customer/${encodeURIComponent(companyName)}/news`);
    return res.data;
};

const NewsPanel = ({ companyName }) => {
    const { data, isLoading, isError } = useQuery({
        queryKey: ['news', companyName],
        queryFn: fetchNews,
        enabled: !!companyName && companyName !== 'All',
        staleTime: 10 * 60 * 1000, // 10 minutes cache
    });

    if (companyName === 'All') return null;

    if (isLoading) {
        return <div style={{ padding: '1rem', textAlign: 'center', fontStyle: 'italic', color: 'var(--text-secondary)' }}>Gathering market intelligence...</div>;
    }

    if (isError) {
        return <div style={{ color: 'var(--danger)', padding: '1rem' }}>Failed to retrieve latest news. Check API keys.</div>;
    }

    const newsList = data?.news || [];

    if (newsList.length === 0) {
        return <div style={{ padding: '1rem', color: 'var(--text-secondary)' }}>No recent news found for {companyName}.</div>;
    }

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1rem' }}>
            {newsList.map((item, idx) => (
                <div key={idx} style={{ paddingBottom: '1rem', borderBottom: idx < newsList.length - 1 ? '1px solid var(--border)' : 'none' }}>
                    <a href={item.url} target="_blank" rel="noopener noreferrer" style={{ fontWeight: '600', display: 'block', marginBottom: '0.25rem' }}>
                        {item.title}
                    </a>
                    {item.snippet && <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{item.snippet}</p>}
                </div>
            ))}
        </div>
    );
};

export default NewsPanel;
