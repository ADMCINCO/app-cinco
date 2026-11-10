import { ActividadFormData } from "@/schemas/actividades.schema";
import { Empleado } from "@/types/empleado";
import { Control, FieldErrors } from "react-hook-form";
import { Actividad } from "./types";

export interface ActividadFormProps {
  defaultValues?: ActividadFormData;
  actividad?: Actividad;
  onSubmit: (data: ActividadFormData) => void;
  isLoading?: boolean;
  backendErrors?: Record<string, any> | null;
  mode?: "create" | "edit";
}

export interface ActividadFormFieldsProps {
  control: Control<ActividadFormData>;
  errors: FieldErrors<ActividadFormData>;
  mode: "create" | "edit";
  selectedEmployee: Empleado | null;
  onEmployeeChange: (empleado: Empleado | null) => void;
  isResponsableDisabled?: boolean;
  employeeError?: string | null;
  onRetryLoadEmployee?: () => void;
}
