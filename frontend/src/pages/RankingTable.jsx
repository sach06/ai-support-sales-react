import React from 'react';
import { useReactTable, getCoreRowModel, flexRender, getSortedRowModel, getPaginationRowModel } from '@tanstack/react-table';
import OpportunityBadge from './OpportunityBadge';

const RankingTable = ({ data, onRowSelect, selectedId, pinnedCompany }) => {
    // Normalise pinned company for case-insensitive comparison
    const pinnedNorm = pinnedCompany && pinnedCompany !== 'All'
        ? pinnedCompany.trim().toLowerCase()
        : null;

    const columns = React.useMemo(() => [
        {
            header: 'Rank',
            accessorFn: (row, i) => i + 1,
            id: 'rank',
            cell: info => <div style={{ fontWeight: 'bold', width: '30px' }}>{info.getValue()}</div>
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
                const isPinned = pinnedNorm && name && name.trim().toLowerCase() === pinnedNorm;
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
            pagination: { pageSize: 10 }
        }
    });

    if (!data || data.length === 0) return <div className="no-data">No ranking data available for these filters.</div>;

    return (
        <div className="ranking-table-container">
            {pinnedNorm && (
                <div className="pinned-company-notice">
                    ⭐ Highlighting <strong>{pinnedCompany}</strong> — your selected company from Global Filters
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
                            const isPinned = pinnedNorm && row.original.company &&
                                row.original.company.trim().toLowerCase() === pinnedNorm;
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

