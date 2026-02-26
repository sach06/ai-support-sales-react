import React from 'react';
import { useReactTable, getCoreRowModel, flexRender, getSortedRowModel, getPaginationRowModel } from '@tanstack/react-table';

const InventoryTable = ({ data }) => {
    const columns = React.useMemo(() => [
        {
            header: 'Company Name',
            accessorKey: 'company_name',
        },
        {
            header: 'Site',
            accessorKey: 'site_name',
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
            header: 'Match Quality',
            accessorKey: 'match_type',
            cell: info => {
                const val = info.getValue() || 'Poor';
                return <span className={`badge badge-${val.toLowerCase()}`}>{val}</span>;
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
