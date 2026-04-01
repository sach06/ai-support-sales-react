import React from 'react';
import { useReactTable, getCoreRowModel, flexRender, getSortedRowModel, getPaginationRowModel } from '@tanstack/react-table';
import OpportunityBadge from './OpportunityBadge';

const normalizeCompanyName = (name) => {
    if (!name) return '';
    return String(name)
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/[^a-zA-Z0-9]/g, '')
        .toLowerCase();
};

const isCompanyMatch = (candidate, target) => {
    const a = normalizeCompanyName(candidate);
    const b = normalizeCompanyName(target);
    if (!a || !b) return false;
    return a === b || a.startsWith(b) || b.startsWith(a) || a.includes(b) || b.includes(a);
};

const formatEvidenceStrength = (score) => {
    if (score >= 8) return 'Very strong';
    if (score >= 6) return 'Strong';
    if (score >= 4) return 'Moderate';
    if (score > 0) return 'Early signal';
    return 'No match yet';
};

const RankingTable = ({ data, onRowSelect, selectedId, pinnedCompany, pinnedGroupKey = null }) => {
    // Normalise pinned company for resilient matching across legal suffix variants.
    const pinnedNorm = pinnedCompany && pinnedCompany !== 'All'
        ? normalizeCompanyName(pinnedCompany)
        : null;

    const columns = React.useMemo(() => [
        {
            header: 'Rank',
            accessorFn: (row) => row.display_rank ?? row.original_rank,
            id: 'rank',
            cell: info => {
                const row = info.row.original;
                const isPinned = pinnedGroupKey
                    ? String(row.company_group_key || '') === String(pinnedGroupKey)
                    : (pinnedNorm && row.company && isCompanyMatch(row.company, pinnedNorm));
                return (
                    <div style={{ fontWeight: 'bold', width: '74px' }} title={row.original_rank ? `Model rank: ${row.original_rank}` : undefined}>
                        {info.getValue()}
                        {isPinned && row.original_rank ? (
                            <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginLeft: '0.25rem' }}>
                                ({row.original_rank})
                            </span>
                        ) : null}
                    </div>
                );
            }
        },
        {
            header: 'Confidence',
            accessorKey: 'priority_score',
            cell: info => {
                const s = typeof info.getValue() === 'number' ? info.getValue() : 0;
                let color = 'inherit';
                if (s > 75) color = 'var(--excellent)';
                else if (s > 50) color = 'var(--good)';
                return <span style={{ fontWeight: '600', color }}>{s.toFixed(1)}%</span>;
            }
        },
        {
            header: 'Company Name',
            accessorKey: 'company',
            cell: info => {
                const name = info.getValue();
                const row = info.row.original;
                const isPinned = pinnedGroupKey
                    ? String(row.company_group_key || '') === String(pinnedGroupKey)
                    : (pinnedNorm && name && isCompanyMatch(name, pinnedNorm));
                return (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: '600' }}>
                        {isPinned && (
                            <span title="Selected in Global Filters" style={{
                                fontSize: '0.65rem', fontWeight: '700', letterSpacing: '0.04em',
                                background: 'linear-gradient(135deg, #f59e0b, #d97706)', color: '#fff',
                                borderRadius: '4px', padding: '1px 5px', whiteSpace: 'nowrap'
                            }}>⭐ YOUR PICK</span>
                        )}
                        {name}
                    </div>
                );
            }
        },
        {
            header: 'Country',
            accessorKey: 'country'
        },
        {
            header: 'Site / City',
            accessorKey: 'site_city',
            cell: info => info.getValue() || <span style={{ color: '#9ca3af', fontStyle: 'italic' }}>Unknown</span>
        },
        {
            header: 'Equipment',
            accessorKey: 'equipment_type'
        },
        {
            header: 'SMS Past Experience Fit',
            accessorKey: 'knowledge_doc_count',
            cell: info => {
                const docs = Math.round(Number(info.getValue() || 0));
                const best = Number(info.row.original.knowledge_best_match_score || 0);
                const avg = Number(info.row.original.knowledge_avg_match_score || 0);
                const theme = info.row.original.knowledge_summary || 'No relevant SMS references yet.';
                return (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', maxWidth: '220px' }}>
                        <span style={{ fontWeight: 600, color: docs > 0 ? 'var(--primary)' : 'var(--text-secondary)' }}>
                            {docs > 0 ? `${docs} relevant SMS references` : 'No relevant references yet'}
                        </span>
                        <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                            Similarity strength: {formatEvidenceStrength(best)}
                            {avg > 0 ? ` (overall ${avg.toFixed(1)})` : ''}
                        </span>
                        <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                            {theme}
                        </span>
                    </div>
                );
            }
        },
        {
            header: 'Opportunity Type & Details',
            accessorKey: 'opportunity_type',
            cell: info => (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <OpportunityBadge type={info.getValue()} />
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', maxWidth: '250px', lineHeight: '1.2' }}>
                        {info.row.original.opportunity_description}
                    </div>
                </div>
            )
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    ], [pinnedNorm]);

    const table = useReactTable({
        data,
        columns,
        getCoreRowModel: getCoreRowModel(),
        getSortedRowModel: getSortedRowModel(),
        getPaginationRowModel: getPaginationRowModel(),
        initialState: {
            pagination: { pageSize: 20 }
        }
    });

    if (!data || data.length === 0) return <div className="no-data">No ranking data available for these filters.</div>;

    return (
        <div className="ranking-table-container">
            {pinnedNorm && (
                <div className="pinned-company-notice">
                    ⭐ {pinnedGroupKey
                        ? <>Showing all branches under <strong>{pinnedCompany}</strong> first. Original model ranks are shown in brackets.</>
                        : <>Showing <strong>{pinnedCompany}</strong> first. Original model rank is shown in brackets.</>}
                </div>
            )}
            <div className="table-scroll-wrapper">
                <table className="data-table ranking-table">
                    <thead>
                        {table.getHeaderGroups().map(headerGroup => (
                            <tr key={headerGroup.id}>
                                {headerGroup.headers.map(header => (
                                    <th
                                        key={header.id}
                                        onClick={header.column.getToggleSortingHandler()}
                                        style={{ cursor: 'pointer' }}
                                    >
                                        {flexRender(header.column.columnDef.header, header.getContext())}
                                        {{ asc: ' 🔼', desc: ' 🔽' }[header.column.getIsSorted()] ?? null}
                                    </th>
                                ))}
                            </tr>
                        ))}
                    </thead>
                    <tbody>
                        {table.getRowModel().rows.map(row => {
                            const isSelected = selectedId === row.original.company;
                            const isPinned = pinnedGroupKey
                                ? String(row.original.company_group_key || '') === String(pinnedGroupKey)
                                : (pinnedNorm && row.original.company && isCompanyMatch(row.original.company, pinnedNorm));
                            return (
                                <tr
                                    key={row.id}
                                    className={`clickable-row ${isSelected ? 'row-selected' : ''} ${isPinned ? 'row-pinned' : ''}`}
                                    onClick={() => onRowSelect(row.original)}
                                >
                                    {row.getVisibleCells().map(cell => (
                                        <td key={cell.id}>
                                            {flexRender(cell.column.columnDef.cell, cell.getContext())}
                                        </td>
                                    ))}
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>

            <div className="table-pagination">
                <button className="btn-secondary" onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()}>Previous</button>
                <span>Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}</span>
                <button className="btn-secondary" onClick={() => table.nextPage()} disabled={!table.getCanNextPage()}>Next</button>
            </div>
        </div>
    );
};

export default RankingTable;

