import { useEffect, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { FieldErrors, useForm, useWatch } from "react-hook-form";
import {
  ActividadSchema,
  ActividadFormData,
} from "@/schemas/actividades.schema";
import { Empleado } from "@/types/empleado";
import { getEmpleadoById, getEmpleadoByCedula } from "@/services/empleado.service";
import { preloadAvatar } from "@/utils/avatar";
import {
  buildResponsableSnapshot,
  getSnapshotEmpleado,
} from "./ActividadForm.utils";
import { getUser } from "@/utils/storage";
import { useBackendErrors } from "@/hooks/useBackendErrors";
import {
  logDevelopmentError,
  logDevelopmentWarning,
} from "@/lib/environment";
import { toast } from "sonner";

interface UseActividadFormLogicParams {
  defaultValues: ActividadFormData;
  backendErrors?: Record<string, any> | null;
  mode?: "create" | "edit";
}

const getFirstFieldErrorMessage = (
  errors: FieldErrors<ActividadFormData>,
): string | undefined => {
  const visit = (value: unknown): string | undefined => {
    if (!value) return undefined;

    if (Array.isArray(value)) {
      for (const item of value) {
        const message = visit(item);
        if (message) return message;
      }
      return undefined;
    }

    if (typeof value === "object") {
      const maybeError = value as { message?: unknown };
      if (typeof maybeError.message === "string" && maybeError.message.trim()) {
        return maybeError.message;
      }

      for (const nestedValue of Object.values(value)) {
        const message = visit(nestedValue);
        if (message) return message;
      }
    }

    return undefined;
  };

  return visit(errors);
};

export const useActividadFormLogic = ({
  defaultValues,
  backendErrors,
  mode = "create",
}: UseActividadFormLogicParams) => {
  const [selectedEmployee, setSelectedEmployee] = useState<Empleado | null>(
    null,
  );
  const [isIdentityResolved, setIsIdentityResolved] = useState<boolean>(
    mode === "edit",
  );
  const [employeeError, setEmployeeError] = useState<string | null>(null);
  const [retryTrigger, setRetryTrigger] = useState<number>(0);

  const {
    control,
    handleSubmit,
    getValues,
    reset,
    setError,
    setValue,
    formState: { errors },
  } = useForm<ActividadFormData>({
    resolver: zodResolver(ActividadSchema) as any,
    defaultValues,
  });

  const watchOts = useWatch({
    control,
    name: "ots",
  });
  const watchFechaInicioPadre = useWatch({
    control,
    name: "fecha_inicio",
  });
  const watchFechaFinPadre = useWatch({
    control,
    name: "fecha_fin_estimado",
  });
  const watchFechaInicioOtPadre = useWatch({
    control,
    name: "ots.0.fecha_inicio",
  });
  const watchFechaFinOtPadre = useWatch({
    control,
    name: "ots.0.fecha_fin",
  });

  // Efecto reactivo para el recálculo e integración de fechas entre OTs Hijas y Actividad Padre
  useEffect(() => {
    if (watchOts && Array.isArray(watchOts) && watchOts.length > 0) {
      // Omitimos la OT padre (índice 0); solo usamos las hijas para extender el rango cuando sea necesario.
      const otsHijas = watchOts.slice(1);

      const hijasInicioDates = otsHijas
        .map((item) => item?.fecha_inicio)
        .filter((d): d is string => !!d && !isNaN(Date.parse(d)));

      const hijasFinDates = otsHijas
        .map((item) => item?.fecha_fin)
        .filter((d): d is string => !!d && !isNaN(Date.parse(d)));

      if (hijasInicioDates.length > 0) {
        const minHijas = hijasInicioDates.reduce((min, curr) => {
          return new Date(curr) < new Date(min) ? curr : min;
        });

        if (
          !watchFechaInicioPadre ||
          new Date(minHijas) < new Date(watchFechaInicioPadre)
        ) {
          setValue("fecha_inicio", minHijas, { shouldValidate: true });
        }
      }

      if (hijasFinDates.length > 0) {
        const maxHijas = hijasFinDates.reduce((max, curr) => {
          return new Date(curr) > new Date(max) ? curr : max;
        });

        if (
          !watchFechaFinPadre ||
          new Date(maxHijas) > new Date(watchFechaFinPadre)
        ) {
          setValue("fecha_fin_estimado", maxHijas, { shouldValidate: true });
        }
      }
    }
  }, [watchOts, watchFechaInicioPadre, watchFechaFinPadre, setValue]);

  // Mantiene sincronizada la OT padre (ots.0) con las fechas generales para que el backend las persista.
  useEffect(() => {
    if (!getValues("ots.0.ot")) {
      return;
    }

    if (watchFechaInicioPadre !== watchFechaInicioOtPadre) {
      setValue("ots.0.fecha_inicio", watchFechaInicioPadre || "", {
        shouldValidate: true,
      });
    }

    if (watchFechaFinPadre !== watchFechaFinOtPadre) {
      setValue("ots.0.fecha_fin", watchFechaFinPadre || "", {
        shouldValidate: true,
      });
    }
  }, [
    getValues,
    setValue,
    watchFechaFinOtPadre,
    watchFechaFinPadre,
    watchFechaInicioOtPadre,
    watchFechaInicioPadre,
  ]);

  useEffect(() => {
    let isActive = true;

    reset(defaultValues);

    const loadEmployee = async () => {
      setEmployeeError(null);

      // Si estamos en modo creación, cargar obligatoriamente el empleado del perfil de sesión
      if (mode === "create") {
        try {
          const user = getUser();
          
          if (!user) {
            logDevelopmentWarning("No user found in session");
            setEmployeeError("No se encontró una sesión de usuario activa.");
            return;
          }
          
          if (!user.username) {
            logDevelopmentWarning("User has no username/cedula:", user);
            setEmployeeError("El usuario en sesión no posee cédula para asociar como responsable.");
            return;
          }

          if (!isActive) return;

          let empleado: Empleado | null = null;
          let fetchFailed = false;

          try {
            empleado = await getEmpleadoByCedula(user.username);
          } catch (err) {
            fetchFailed = true;
            if (user.id && Number(user.id) > 0) {
              try {
                empleado = await getEmpleadoById(Number(user.id));
                fetchFailed = false;
              } catch {
                empleado = null;
              }
            }
          }

          if (!isActive) return;

          const userCedula = String(user.username).trim().toLowerCase();
          const userId = Number(user.id);
          const isExactMatch =
            Boolean(empleado) &&
            (String(empleado?.cedula || "").trim().toLowerCase() === userCedula ||
              empleado?.id === userId);

          if (empleado && isExactMatch) {
            setSelectedEmployee(empleado);
            setIsIdentityResolved(true);
            setEmployeeError(null);
            setValue("responsable_id", empleado.id);
            setValue("responsable_snapshot", buildResponsableSnapshot(empleado));

            if (empleado.link_foto) {
              preloadAvatar(empleado.link_foto);
            }
          } else {
            // Descartar coincidencias parciales: si no hay coincidencia exacta por cédula ni ID, no asignar responsable
            setSelectedEmployee(null);
            setIsIdentityResolved(false);
            setValue("responsable_id", 0);
            setEmployeeError(
              fetchFailed
                ? "Error de conexión al consultar el perfil de empleado."
                : "No se encontró un empleado activo que coincida exactamente con tu cédula o ID."
            );
          }
        } catch (error) {
          if (!isActive) return;
          setSelectedEmployee(null);
          setIsIdentityResolved(false);
          setValue("responsable_id", 0);
          setEmployeeError(
            "Error al consultar el perfil de empleado: " +
              (error instanceof Error ? error.message : "Error de red")
          );
          logDevelopmentWarning(
            "Could not load employee for current user:",
            error instanceof Error ? error.message : String(error),
          );
        }
        return;
      }

      // Modo edición o ya hay un responsable
      if (defaultValues.responsable_id && defaultValues.responsable_id > 0) {
        try {
          const empleadoBase = getSnapshotEmpleado(defaultValues);

          if (empleadoBase && isActive) {
            setSelectedEmployee(empleadoBase);
          }

          const empleadoFull = await getEmpleadoById(
            defaultValues.responsable_id,
          );
          if (!isActive) return;

          setSelectedEmployee({
            ...empleadoBase,
            ...empleadoFull,
          });

          preloadAvatar(empleadoFull.link_foto);
        } catch (error) {
          logDevelopmentError("Error preloading employee:", error);
        }
      } else if (isActive) {
        setSelectedEmployee(null);
      }
    };

    loadEmployee();

    return () => {
      isActive = false;
    };
  }, [defaultValues, reset, mode, setValue, retryTrigger]);

  // Aplicar errores del backend al formulario
  useBackendErrors(backendErrors, setError);

  const retryLoadEmployee = () => {
    setRetryTrigger((prev) => prev + 1);
  };

  const handleEmployeeChange = (empleado: Empleado | null) => {
    setSelectedEmployee(empleado);
    setValue("responsable_id", empleado?.id ?? 0);

    if (empleado) {
      setValue("responsable_snapshot", buildResponsableSnapshot(empleado));
    }
  };

  const handleInvalidSubmit = (formErrors: FieldErrors<ActividadFormData>) => {
    const firstMessage = getFirstFieldErrorMessage(formErrors);

    toast.error(
      firstMessage || "Completa los campos obligatorios antes de guardar.",
    );
  };

  return {
    control,
    errors,
    handleSubmit,
    handleInvalidSubmit,
    selectedEmployee,
    handleEmployeeChange,
    isIdentityResolved,
    employeeError,
    retryLoadEmployee,
  };
};
