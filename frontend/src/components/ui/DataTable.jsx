import React from 'react';

export default function DataTable({ columns, children }) {
  return (
    <div className="rounded-md border border-border bg-card flex-1 overflow-hidden relative">
      <div className="absolute inset-0 overflow-auto">
        <table className="w-full caption-bottom text-sm text-left">
          <thead className="[&_tr]:border-b border-border sticky top-0 bg-card z-10">
            <tr className="border-b border-border transition-colors hover:bg-muted/50">
              {columns.map((column, index) => (
                <th
                  key={column.key || index}
                  className={`h-12 px-4 align-middle font-medium text-gray-400 ${
                    column.align === 'right' ? 'text-right' : ''
                  } ${column.className || ''}`}
                >
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="[&_tr:last-child]:border-0">{children}</tbody>
        </table>
      </div>
    </div>
  );
}
