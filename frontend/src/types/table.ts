import {
  ColumnDef,
  ColumnFiltersState,
  SortingState,
  VisibilityState,
} from "@tanstack/react-table";
import { ReactNode } from "react";

interface DataTableProps<TData> {
  data: TData[];
  columns: ColumnDef<TData>[];

  isLoading?: boolean;
  emptyMessage?: string;

  enablePagination?: boolean;
  pageSize?: number;

  enableGlobalFilter?: boolean;
  enableColumnFilters?: boolean;
  enableSorting?: boolean;
  enableColumnVisibility?: boolean;

  globalFilterPlaceholder?: string;
  enablePageSizeSelector?: boolean;
  pageSizeOptions?: number[];

  initialGlobalFilter?: string;
  initialColumnFilters?: ColumnFiltersState;
  initialSorting?: SortingState;
  initialColumnVisibility?: VisibilityState;

  globalFilterValue?: string;
  columnFiltersValue?: ColumnFiltersState;
  sortingValue?: SortingState;
  columnVisibilityValue?: VisibilityState;
  pageIndexValue?: number;
  pageSizeValue?: number;

  onGlobalFilterChange?: (value: string) => void;
  onColumnFiltersChange?: (filters: ColumnFiltersState) => void;
  onSortingChange?: (sorting: SortingState) => void;
  onColumnVisibilityChange?: (visibility: VisibilityState) => void;
  onPageChange?: (pageIndex: number) => void;
  onPageSizeChange?: (pageSize: number) => void;
  onVisibleDataChange?: (rows: TData[]) => void;

  onRowClick?: (row: TData) => void;
  renderRowActions?: (row: TData) => ReactNode;
  toolbarActions?: ReactNode;
  tableContainerClassName?: string;
}

export type { DataTableProps };
