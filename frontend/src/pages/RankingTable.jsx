import React from 'react';
import { useReactTable, getCoreRowModel, flexRender, getSortedRowModel, getPaginationRowModel } from '@tanstack/react-table';
import OpportunityBadge from './OpportunityBadge';

const RankingTable = ({ data, onRowSelect, selectedId }) => {
    const columns = React.useMemo(() => [
        {
            header: 'Rank',
            accessorFn: (row, i) => i + 1,
            id: 'rank',
            cell: info => <div style={{ fontWeight: 'bold', width: '30px' }}>{info.getValue()}</div>
        },
        {
            header: 'Score',
            accessorKey: 'score',
            cell: info => {
                const s = info.getValue() * 100;
                let color = 'inherit';
                if (s > 75) color = 'var(--excellent)';
                else if (s > 50) color = 'var(--good)';
                return <span style={{ fontWeight: '600', color }}>{s.toFixed(1)}</span>;
            }
        },
        {
            header: 'Company Name',
            accessorKey: 'company_name',
            cell: info => <div style={{ fontWeight: '600' }}>{info.getValue()}</div>
        },
        {
            header: 'Country',
            accessorKey: 'country'
        },
        {
            header: 'Equipment',
            accessorKey: 'equipment_type'
        },
        {
            header: 'Opportunity Type',
            accessorKey: 'opportunity_type',
            cell: info => <OpportunityBadge type={info.getValue()} />
        }
    ], []);

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
                            const isSelected = selectedId === row.original.id; // requires an id or use id from array
                            return (
                                <tr
                                    key={row.id}
                                    className={`clickable-row ${isSelected ? 'row-selected' : ''}`}
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
