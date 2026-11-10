import { DataTable } from "@/components/common/DataTable";
import { GestionActividadesTableProps } from "../gestionActividadesView.types";
import { ACTIVIDAD_TABLE_CONFIG } from "../actividadTable.utils";

export const GestionActividadesTable = ({
  actividades,
  columns,
  globalFilter,
  setGlobalFilter,
  sorting,
  setSorting,
  pageIndex,
  setPageIndex,
  pageSize,
  setPageSize,
  visibleRows,
  setVisibleRows,
  toolbarActions,
}: GestionActividadesTableProps & { toolbarActions?: React.ReactNode }) => {
  return (
    <DataTable
      data={actividades}
      columns={columns}
      enablePagination
      pageSize={ACTIVIDAD_TABLE_CONFIG.defaultPageSize}
      emptyMessage="No hay actividades para mostrar."
      enableGlobalFilter
      enableSorting
      enableColumnFilters
      enableColumnVisibility
      pageSizeOptions={[5, 10, 25, 50, 100]}
      globalFilterValue={globalFilter}
      sortingValue={sorting}
      pageIndexValue={pageIndex}
      pageSizeValue={pageSize}
      onGlobalFilterChange={(value) => {
        setGlobalFilter(value);
        setPageIndex(0);
      }}
      onSortingChange={(nextSorting) => {
        setSorting(nextSorting);
        setPageIndex(0);
      }}
      onPageChange={setPageIndex}
      onPageSizeChange={(size) => {
        setPageSize(size);
        setPageIndex(0);
      }}
      onVisibleDataChange={setVisibleRows}
      toolbarActions={toolbarActions}
      tableContainerClassName="max-h-[calc(100vh-380px)] min-h-[350px] overflow-auto"
    />
  );
};
