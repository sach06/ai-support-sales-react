import React from 'react';
import { useReactTable, getCoreRowModel, flexRender, getSortedRowModel, getPaginationRowModel } from '@tanstack/react-table';

const InventoryTable = ({ data }) => {
    const columns = React.useMemo(() => [
        {
            header: 'Company Name',
            id: 'company_name',
            accessorFn: row => row.name || row.company_internal || row['Parent Company'] || '—',
        },
        {
            header: 'Site',
            id: 'site',
            accessorFn: row => row.City || row.site_name || '—',
        },
        {
            header: 'Country',
            accessorKey: 'country',
        },
        {
            header: 'Equipment',
            accessorKey: 'equipment_type',
        },
        {
            header: 'Capacity',
            id: 'capacity',
            accessorFn: row => row.capacity || row.capacity_internal || row['Nominal Capacity'] || '—',
            cell: info => {
                const val = info.getValue();
                return val !== '—' ? `${val.toLocaleString()} kt/y` : val;
            }
        },
        {
            header: 'Status',
            id: 'status',
            accessorFn: row => row.status_internal || row['Status of the Plant'] || 'Unknown',
            cell: info => {
                const status = info.getValue();
                const sLower = String(status).toLowerCase();
                let cls = 'badge-okay';
                if (sLower.includes('operating')) cls = 'badge-excellent';
                else if (sLower.includes('project') || sLower.includes('construction')) cls = 'badge-good';
                else if (sLower.includes('shut down') || sLower.includes('idle') || sLower.includes('abandoned')) cls = 'badge-poor';

                return <span className={`badge ${cls}`}>{status}</span>;
            }
        },
        {
            header: 'Match Quality',
            id: 'match_quality',
            accessorFn: row => {
                const score = row['Matching Quality %'];
                if (score === null || score === undefined) return null;
                return Number(score);
            },
            cell: info => {
                const score = info.getValue();
                if (score === null || score === undefined) {
                    return <span className="badge badge-poor">Poor</span>;
                }
                let label = 'Excellent';
                if (score < 50) label = 'Poor';
                else if (score < 80) label = 'Okay';
                else if (score < 95) label = 'Good';
                return <span className={`badge badge-${label.toLowerCase()}`}>{label} ({Math.round(score)}%)</span>;
            }
        },
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

    if (!data || data.length === 0) return <div>No inventory data for the selected filters.</div>;

    return (
        <div>
            <div style={{ maxHeight: '400px', overflowY: 'auto', border: '1px solid var(--border)', borderRadius: '4px' }}>
                <table className="data-table">
                    <thead>
                        {table.getHeaderGroups().map(headerGroup => (
                            <tr key={headerGroup.id}>
                                {headerGroup.headers.map(header => (
                                    <th key={header.id} onClick={header.column.getToggleSortingHandler()} style={{ cursor: 'pointer' }}>
                                        {flexRender(header.column.columnDef.header, header.getContext())}
                                        {{ asc: ' 🔼', desc: ' 🔽' }[header.column.getIsSorted()] ?? null}
                                    </th>
                                ))}
                            </tr>
                        ))}
                    </thead>
                    <tbody>
                        {table.getRowModel().rows.map(row => (
                            <tr key={row.id}>
                                {row.getVisibleCells().map(cell => (
                                    <td key={cell.id}>
                                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            <div style={{ marginTop: '1rem', display: 'flex', gap: '1rem', alignItems: 'center', justifyContent: 'center' }}>
                <button onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()}>Prev</button>
                <span>Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}</span>
                <button onClick={() => table.nextPage()} disabled={!table.getCanNextPage()}>Next</button>
            </div>
        </div>
    );
};

export default InventoryTable;
