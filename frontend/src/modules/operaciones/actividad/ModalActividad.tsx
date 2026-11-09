"use client";

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

  const defaultValues =
    mode === "edit" && actividad
      ? actividadEditDefaultValues(actividad)
      : actividadCreateDefaultValues;

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
          defaultValues={defaultValues}
          isLoading={isLoading}
          onSubmit={(data) =>
            handleSubmit(
              data,
              mode,
              actividad?.id,
              closeModal,
              actividad?.responsable_id,
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
