import { Table as ReactTable } from "@tanstack/react-table";
import { Table } from "@/components/ui/table";
import { DataTableHeaderComponent } from "./DataTableHeader";
import { DataTableBodyComponent } from "./DataTableBody";

interface DataTableDesktopProps<TData> {
  table: ReactTable<TData>;
  isLoading: boolean;
  emptyMessage: string;
  enableSorting: boolean;
  enableColumnFilters: boolean;
  onRowClick?: (row: TData) => void;
  tableContainerClassName?: string;
}

/**
 * Componente que renderiza la vista completa de la tabla para escritorio.
 * Combina el header y body en una tabla HTML responsiva.
 *
 * @template TData - Tipo de datos de la tabla
 */
export function DataTableDesktop<TData>({
  table,
  isLoading,
  emptyMessage,
  enableSorting,
  enableColumnFilters,
  onRowClick,
  tableContainerClassName,
}: DataTableDesktopProps<TData>) {
  const headerGroups = table.getHeaderGroups();
  const rows = table.getRowModel().rows;
  const visibleColumnsCount = table.getVisibleLeafColumns().length;

  return (
    <div
      className={
        tableContainerClassName
          ? `hidden w-full min-w-0 max-w-full overflow-auto md:block ${tableContainerClassName}`
          : "hidden h-full w-full min-w-0 max-w-full overflow-auto md:block"
      }
    >
      <Table>
        <DataTableHeaderComponent
          headerGroups={headerGroups}
          enableSorting={enableSorting}
          enableColumnFilters={enableColumnFilters}
        />
        <DataTableBodyComponent
          rows={rows}
          visibleColumnsCount={visibleColumnsCount}
          isLoading={isLoading}
          emptyMessage={emptyMessage}
          onRowClick={onRowClick}
        />
      </Table>
    </div>
  );
}
