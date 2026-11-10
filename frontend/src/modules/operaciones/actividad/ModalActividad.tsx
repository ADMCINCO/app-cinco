"use client";

import { useMemo } from "react";
import {
  actividadCreateDefaultValues,
  actividadEditDefaultValues,
} from "./actividad.defaults";
import { Actividad } from "./types";
import { useModal } from "@/hooks/useModal";
import ActividadForm from "./ActividadForm";
import { Modal } from "@/components/ui/modal";
import Button from "@/components/ui/button/Button";
import { useActividadSubmit } from "./useActividadSubmit";

interface ModalActividadProps {
  mode: "create" | "edit";
  actividad?: Actividad;
  textButton?: string;
  iconButton?: React.ReactNode;
}

const ModalActividad = ({
  mode,
  actividad,
  textButton,
  iconButton,
}: ModalActividadProps) => {
  const { isOpen, openModal, closeModal } = useModal();
  const { handleSubmit, isLoading, error } = useActividadSubmit();

  const defaultValues = useMemo(() => {
    return mode === "edit" && actividad
      ? actividadEditDefaultValues(actividad)
      : actividadCreateDefaultValues;
  }, [mode, actividad]);

  const initialResponsableId =
    actividad?.responsable_snapshot?.empleado_id || actividad?.responsable_id;

  return (
    <>
      <Button onClick={openModal} startIcon={iconButton}>
        {textButton}
      </Button>

      <Modal isOpen={isOpen} onClose={closeModal} className="max-w-150 p-5">
        <div className="mb-6 text-lg font-medium">
          {mode === "create" ? "Crear Nueva Actividad" : "Editar Actividad"}
        </div>

        <ActividadForm
          actividad={actividad}
          defaultValues={defaultValues}
          isLoading={isLoading}
          onSubmit={(data) =>
            handleSubmit(
              data,
              mode,
              actividad?.id,
              closeModal,
              initialResponsableId,
            )
          }
          backendErrors={error?.errors}
          mode={mode}
        />
      </Modal>
    </>
  );
};

export default ModalActividad;
