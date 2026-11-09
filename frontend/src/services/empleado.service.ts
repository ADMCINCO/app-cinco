// src/services/empleado.service.ts
import api from "@/lib/api";
import { Empleado } from "@/types/empleado";
import { cache } from "@/lib/cache";

const CACHE_TTL = {
  ALL_EMPLOYEES: 10 * 60 * 1000, // 10 minutos para lista completa
  SEARCH: 5 * 60 * 1000, // 5 minutos para búsquedas
  SINGLE: 15 * 60 * 1000, // 15 minutos para empleado individual
};

export const getEmpleados = async (): Promise<Empleado[]> => {
  return cache.getOrFetch(
    "empleados:all",
    async () => {
      const res = await api.get("/empleados/empleados/");
      return res.data;
    },
    CACHE_TTL.ALL_EMPLOYEES,
  );
};

export const searchEmpleados = async (
  query: string,
  includeInactive = false,
): Promise<Empleado[]> => {
  const cacheKey = `empleados:search:${query.toLowerCase().trim()}:${includeInactive}`;

  return cache.getOrFetch(
    cacheKey,
    async () => {
      const params: any = { search: query };
      if (includeInactive) {
        params.estado = "all";
      }
      const res = await api.get("/empleados/empleados/", { params });
      return res.data;
    },
    CACHE_TTL.SEARCH,
  );
};

export const getEmpleadoByCedula = async (
  cedula: string,
): Promise<Empleado> => {
  const cleanCedula = String(cedula).trim();
  const cacheKey = `empleados:cedula:${cleanCedula}`;

  return cache.getOrFetch(
    cacheKey,
    async () => {
      // Buscar empleado por cédula usando el endpoint de búsqueda
      const res = await api.get("/empleados/empleados/", {
        params: { search: cleanCedula },
      });
      
      const items: Empleado[] = Array.isArray(res.data) ? res.data : res.data?.results || [];
      // Aceptar únicamente empleados cuya cédula o ID coincida exactamente, descartando coincidencias parciales
      const target = cleanCedula.toLowerCase();
      const empleado = items.find((emp: Empleado) => {
        const empCedula = String(emp.cedula || "").trim().toLowerCase();
        const empId = String(emp.id || "").trim();
        return empCedula === target || empId === target;
      });
      
      if (!empleado) {
        throw new Error(`Empleado con cédula o ID ${cleanCedula} no encontrado`);
      }
      
      return empleado;
    },
    CACHE_TTL.SINGLE,
  );
};

export const getEmpleadoById = async (id: number): Promise<Empleado> => {
  const cacheKey = `empleados:id:${id}`;

  return cache.getOrFetch(
    cacheKey,
    async () => {
      const res = await api.get(`/empleados/empleados/${id}/`);
      return res.data;
    },
    CACHE_TTL.SINGLE,
  );
};

export interface CertificadoLaboralManualData {
  salario?: string | number;
  tipo_contrato?: string;
  cargo?: string;
  fecha_ingreso?: string;
  fecha_egreso?: string;
  estado?: string;
  genero?: string;
}

export const downloadCertificadoLaboral = async (
  id: number,
  documentType?: "CC" | "PT" | "TI" | "CE",
  manualData?: CertificadoLaboralManualData,
): Promise<{ blob: Blob; filename: string }> => {
  const hasManualData = Boolean(
    manualData && Object.values(manualData).some((val) => val !== undefined && val !== ""),
  );

  const response = hasManualData
    ? await api.post(
        `/empleados/empleados/${id}/certificado-laboral/`,
        {
          document_type: documentType,
          ...manualData,
        },
        {
          responseType: "blob",
          timeout: 60000,
        },
      )
    : await api.get(`/empleados/empleados/${id}/certificado-laboral/`, {
        params: documentType ? { document_type: documentType } : undefined,
        responseType: "blob",
        timeout: 60000,
      });

  const contentDisposition = String(
    response.headers["content-disposition"] || "",
  );
  const filenameMatch = contentDisposition.match(/filename="([^"]+)"/i);

  return {
    blob: response.data as Blob,
    filename: filenameMatch?.[1] || `certificado_laboral_${id}.pdf`,
  };
};

/**
 * Limpiar el caché de empleados
 * Útil cuando se actualiza, crea o elimina un empleado
 */
export const clearEmpleadosCache = (): void => {
  // Obtener todas las claves del caché
  const stats = cache.getStats();

  // Eliminar todas las claves que comiencen con "empleados:"
  stats.keys.forEach((key) => {
    if (key.startsWith("empleados:")) {
      cache.delete(key);
    }
  });
};

export interface CertificadoFirmaConfigData {
  firmante_nombre: string;
  firmante_cargo: string;
  firma_imagen_nombre: string;
  can_edit: boolean;
}

export const getCertificadoFirmaConfig = async (): Promise<CertificadoFirmaConfigData> => {
  const res = await api.get("/empleados/empleados/certificado-config/");
  return res.data;
};

export const updateCertificadoFirmaConfig = async (
  formData: FormData,
): Promise<CertificadoFirmaConfigData> => {
  const res = await api.post("/empleados/empleados/certificado-config/update/", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
  return res.data;
};

