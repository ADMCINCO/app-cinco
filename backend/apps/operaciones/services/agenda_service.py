import calendar
import csv
import io
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.operaciones.models.actividad_model import Actividad, ActividadOT
from apps.operaciones.models.agenda_model import (
    Agenda,
    AgendaTecnicoRegistro,
    AgendaTrabajo,
    InfraestructuraParametros,
)
from apps.operaciones.serializers.agenda_serializer import AgendaReadSerializer

User = get_user_model()


def array_rango_fechas(fecha_inicio_str: str, fecha_fin_str: str) -> List[str]:
    """
    Genera la lista de fechas consecutivas (YYYY-MM-DD) entre dos fechas inclusive.
    """
    try:
        f_ini = datetime.strptime(str(fecha_inicio_str).strip(), "%Y-%m-%d").date()
        f_fin = datetime.strptime(str(fecha_fin_str).strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        return []

    if f_fin < f_ini:
        return []

    dias = (f_fin - f_ini).days + 1
    return [(f_ini + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(dias)]


class AgendaService:
    @staticmethod
    def get_agendas_mes(
        mes: Optional[str] = None,
        yyyy: Optional[str] = None,
        sede: Optional[str] = None,
        fecha_inicio: Optional[Any] = None,
        fecha_fin: Optional[Any] = None,
        responsable_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Consulta todos los agendamientos de `operaciones_agenda` para el rango, mes y sede dados.
        Aplica select_related para traer en una sola consulta: Actividad, Ubicación y Responsable.
        """
        qs = Agenda.objects.select_related(
            "actividad",
            "actividad__ubicacion",
            "actividad__detalle",
            "actividad__responsable_snapshot",
            "responsable",
        ).filter(is_deleted=False)

        # Filtro por mes y año
        if mes and yyyy:
            try:
                mes_int = int(mes)
                yyyy_int = int(yyyy)
                _, ultimo_dia = calendar.monthrange(yyyy_int, mes_int)
                ini_mes = date(yyyy_int, mes_int, 1)
                fin_mes = date(yyyy_int, mes_int, ultimo_dia)

                # Traer agendamientos que se solapen con el mes consultado
                qs = qs.filter(fecha_inicio__lte=fin_mes, fecha_fin__gte=ini_mes)
            except (ValueError, TypeError):
                pass

        # Filtro por rango de fechas explícito
        if fecha_inicio:
            qs = qs.filter(fecha_fin__gte=fecha_inicio)
        if fecha_fin:
            qs = qs.filter(fecha_inicio__lte=fecha_fin)

        # Filtro por sede
        if sede and str(sede).strip():
            qs = qs.filter(sede__iexact=str(sede).strip())

        # Filtro por responsable
        if responsable_id:
            qs = qs.filter(responsable_id=responsable_id)

        # Serializar y retornar
        serializer = AgendaReadSerializer(qs.order_by("fecha_inicio", "id"), many=True)
        return serializer.data

    @staticmethod
    def get_tecnicos_activos(sede: Optional[str] = None, dias_recientes: int = 30) -> List[Dict[str, Any]]:
        """
        Lista los técnicos que tienen agendamientos activos o creados en el último mes (30 días).
        Si aún no hay agendamientos en el sistema, incluye técnicos activos para permitir iniciar el agendamiento.
        """
        fecha_limite = timezone.now().date() - timedelta(days=dias_recientes)
        
        # 1. Obtener IDs de responsables con agendamientos recientes
        agendas_qs = Agenda.objects.filter(
            fecha_fin__gte=fecha_limite,
            is_deleted=False
        )
        if sede and str(sede).strip():
            agendas_qs = agendas_qs.filter(sede__iexact=str(sede).strip())

        ids_con_agenda = set(agendas_qs.values_list("responsable_id", flat=True).distinct())

        # 2. Consultar usuarios en auth_user
        if ids_con_agenda:
            usuarios = User.objects.filter(id__in=ids_con_agenda, is_active=True)
        else:
            # Si no hay agendas previas en esa sede, listamos los usuarios activos
            usuarios = User.objects.filter(is_active=True)[:50]

        # Consultar datos oficiales desde la tabla Empleado si existen
        empleados_map = {}
        cedulas = [u.username for u in usuarios if u.username]
        if cedulas:
            try:
                from apps.empleados.models.empleado_model import Empleado
                for emp in Empleado.objects.filter(cedula__in=cedulas):
                    empleados_map[str(emp.cedula)] = emp
            except Exception:
                pass

        resultado = []
        for u in usuarios:
            cedula_user = str(getattr(u, "username", u.id))
            emp_base = empleados_map.get(cedula_user)

            # 1. Si existe en la tabla de Empleados
            if emp_base:
                nombre = f"{emp_base.nombre} {emp_base.apellido}".strip() or u.get_full_name().strip()
                area = emp_base.area or "OPERACIONES"
                carpeta = emp_base.carpeta or "RESIDENCIAL"
                cargo = emp_base.cargo or "TÉCNICO"
                movil = emp_base.movil or ""
                emp_sede = emp_base.sede or sede or "MEDELLIN"
            else:
                # 2. Si no, consultar en el snapshot de actividad
                snapshot = (
                    Actividad.objects.filter(responsable_id=u.id, is_deleted=False)
                    .select_related("responsable_snapshot")
                    .first()
                )
                resp_snapshot = getattr(snapshot, "responsable_snapshot", None) if snapshot else None

                nombre = u.get_full_name().strip() or (resp_snapshot.nombre if resp_snapshot else u.username)
                area = resp_snapshot.area if resp_snapshot else "OPERACIONES"
                carpeta = resp_snapshot.carpeta if resp_snapshot else "RESIDENCIAL"
                cargo = resp_snapshot.cargo if resp_snapshot else "TÉCNICO"
                movil = resp_snapshot.movil if resp_snapshot else ""
                emp_sede = sede or "MEDELLIN"

            resultado.append({
                "id": u.id,
                "empleado_id": u.id,
                "cedula": cedula_user,
                "nombre": nombre,
                "apellido": emp_base.apellido if emp_base else "",
                "email": u.email,
                "sede": emp_sede,
                "area": area,
                "carpeta": carpeta,
                "cargo": cargo,
                "movil": movil,
                "link_foto": getattr(emp_base, "link_foto", "") if emp_base else "",
            })

        return resultado

    @staticmethod
    def buscar_actividad_por_ot(ot: str) -> Optional[Dict[str, Any]]:
        """
        Busca una OT en `operaciones_actividades` o `operaciones_actividad_ots` para autocompletar la agenda.
        """
        ot_limpia = str(ot).strip()
        if not ot_limpia:
            return None

        # 1. Buscar en ActividadOT
        rel_ot = ActividadOT.objects.select_related("actividad").filter(
            ot__iexact=ot_limpia,
            is_active=True
        ).first()

        actividad = rel_ot.actividad if rel_ot else None

        # 2. Si no encontró, buscar directamente en Actividad
        if not actividad:
            actividad = Actividad.objects.filter(ot__iexact=ot_limpia, is_deleted=False).first()

        if not actividad:
            return None

        detalle = getattr(actividad, "detalle", None)
        ubicacion = getattr(actividad, "ubicacion", None)
        responsable_snap = getattr(actividad, "responsable_snapshot", None)

        # Buscar usuario en auth_user correspondiente al responsable
        usuario = User.objects.filter(id=actividad.responsable_id).first()
        nombre_tecnico = ""
        if responsable_snap and responsable_snap.nombre:
            nombre_tecnico = responsable_snap.nombre
        elif usuario:
            nombre_tecnico = usuario.get_full_name() or usuario.username

        f_ini = actividad.fecha_inicio.strftime("%Y-%m-%d") if actividad.fecha_inicio else (actividad.created_at.date().strftime("%Y-%m-%d") if actividad.created_at else None)
        f_fin = actividad.fecha_fin_estimado.strftime("%Y-%m-%d") if actividad.fecha_fin_estimado else f_ini

        area = responsable_snap.area if (responsable_snap and responsable_snap.area) else ""
        carpeta = responsable_snap.carpeta if (responsable_snap and responsable_snap.carpeta) else ""
        cargo = responsable_snap.cargo if (responsable_snap and responsable_snap.cargo) else ""
        movil = responsable_snap.movil if (responsable_snap and responsable_snap.movil) else ""

        if (not area or not carpeta) and usuario and usuario.username:
            try:
                from apps.empleados.models.empleado_model import Empleado
                emp = Empleado.objects.filter(cedula=usuario.username).first()
                if emp:
                    if not area and emp.area:
                        area = emp.area
                    if not carpeta and emp.carpeta:
                        carpeta = emp.carpeta
                    if not cargo and emp.cargo:
                        cargo = emp.cargo
                    if not movil and emp.movil:
                        movil = emp.movil
            except Exception:
                pass

        return {
            "id": actividad.id,
            "actividad_id": actividad.id,
            "ot": ot_limpia,
            "estado": actividad.estado,
            "fecha_inicio": f_ini,
            "fecha_fin_estimado": f_fin,
            "tipo_trabajo": detalle.tipo_trabajo if detalle else "",
            "descripcion": detalle.descripcion if detalle else "",
            "direccion": ubicacion.direccion if ubicacion else "",
            "zona": ubicacion.zona if ubicacion else "",
            "nodo": ubicacion.nodo if ubicacion else "",
            "longitud": ubicacion.coordenada_x if ubicacion else "",
            "latitud": ubicacion.coordenada_y if ubicacion else "",
            "responsable_id": actividad.responsable_id,
            "responsable_nombre": nombre_tecnico,
            "responsable_area": area,
            "responsable_carpeta": carpeta,
            "responsable_cargo": cargo,
            "responsable_movil": movil,
        }

    @staticmethod
    def save_agenda(data: Dict[str, Any], user: Optional[Any] = None) -> Dict[str, Any]:
        """
        Crea o actualiza un agendamiento en la tabla `operaciones_agenda`.

        Soporta el formato relacional y retrocompatibilidad con `data_form`.
        Preserva los datos macro de la actividad (no sobreescribe responsable ni fechas de OTs).

        Args:
            data: Diccionario con la información del agendamiento y técnico asignado.
            user: Usuario autenticado que realiza la operación.

        Returns:
            Dict[str, Any]: Diccionario con el resultado de la operación y el registro persistido.

        Raises:
            ValueError: Si los datos son inválidos, las fechas son incorrectas o no existe la actividad.
        """
        if not data or not isinstance(data, dict):
            raise ValueError("No se recibieron datos válidos para agendar.")

        # Extraer campos soportando payload plano o data_form anidado
        data_form = data.get("data_form", data)
        agenda_id = data.get("id") or data_form.get("id")

        # 1. Resolver Actividad ID
        actividad_id = data.get("actividad_id") or data_form.get("actividad_id") or data_form.get("legacy_actividad_id")
        ot = str(data_form.get("actividad_param") or data_form.get("ot") or "").strip()

        if not actividad_id and ot:
            act_info = AgendaService.buscar_actividad_por_ot(ot)
            if act_info:
                actividad_id = act_info["id"]

        if not actividad_id:
            raise ValueError("Debe especificar una actividad u OT válida para realizar el agendamiento.")

        actividad = Actividad.objects.filter(id=actividad_id, is_deleted=False).first()
        if not actividad:
            raise ValueError(f"No se encontró la actividad con ID {actividad_id}.")

        # 2. Resolver Responsable (auth_user)
        # En la UI, el líder interactúa con un componente buscador asistido (EmployeeSearchInput)
        # que permite coincidencias multi-criterio: nombres (uno o ambos), apellidos (uno o ambos),
        # cédula o móvil. Al seleccionar al colaborador de la lista enriquecida, el frontend vincula
        # la cédula verificada en `cc_agen_tecnico_search` y el identificador en `responsable_id`.
        raw_responsable = (
            data.get("responsable_id")
            or data_form.get("responsable_id")
            or data_form.get("empleado_id")
            or data_form.get("iduser")
        )
        cc_search = data_form.get("cc_agen_tecnico_search") if isinstance(data_form, dict) else None
        responsable = None

        if cc_search and str(cc_search).strip():
            ced = str(cc_search).strip()
            responsable = User.objects.filter(username=ced, is_active=True).first()
            if not responsable:
                raise ValueError(f"El técnico con cédula '{ced}' no existe o no se encuentra activo en el sistema.")
        elif raw_responsable:
            raw_str = str(raw_responsable).strip()
            responsable = User.objects.filter(
                Q(id=int(raw_str) if raw_str.isdigit() else 0) | Q(username=raw_str),
                is_active=True,
            ).first()
            if not responsable:
                raise ValueError(f"El técnico con identificador '{raw_str}' no existe o no se encuentra activo en el sistema.")
        else:
            # Fallback a actividad.responsable únicamente cuando el cliente no envió ningún responsable
            if actividad.responsable_id:
                responsable = User.objects.filter(id=actividad.responsable_id, is_active=True).first()

            if not responsable:
                raise ValueError("No se pudo determinar un técnico responsable activo para el agendamiento.")

        # 3. Fechas
        f_ini_str = str(data.get("fecha_inicio") or data_form.get("fec_agen_ini") or data_form.get("fecha_inicio") or "").strip()
        f_fin_str = str(data.get("fecha_fin") or data_form.get("fec_agen_fin") or data_form.get("fecha_fin") or "").strip()

        if not f_ini_str or not f_fin_str:
            raise ValueError("Las fechas de inicio y fin son obligatorias.")

        try:
            f_ini = datetime.strptime(f_ini_str, "%Y-%m-%d").date()
            f_fin = datetime.strptime(f_fin_str, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Formato de fecha inválido. Debe ser YYYY-MM-DD.")

        if f_fin < f_ini:
            raise ValueError("La fecha fin no puede ser anterior a la fecha de inicio.")

        # 4. Sede y Metadatos
        sede = str(data.get("sede") or data_form.get("rad_sede_agen") or data_form.get("sede") or "medellin").strip()
        color_hex = str(data.get("color_hex") or data_form.get("color_hex") or "#66bb6a").strip()
        observacion = str(data.get("observacion") or data_form.get("observaciones_dia") or data_form.get("observacion") or "").strip()

        # 5. Guardar en Base de Datos
        user_auth = user if (user and getattr(user, "is_authenticated", False)) else None

        with transaction.atomic():
            if agenda_id:
                agenda = Agenda.objects.filter(id=agenda_id, is_deleted=False).first()
                if not agenda:
                    raise ValueError(f"No se encontró el agendamiento con ID {agenda_id} para actualizar.")
                
                agenda.actividad = actividad
                agenda.responsable = responsable
                agenda.fecha_inicio = f_ini
                agenda.fecha_fin = f_fin
                agenda.sede = sede
                agenda.color_hex = color_hex
                agenda.observacion = observacion
                if user_auth:
                    agenda.updated_by = user_auth
                agenda.save()
                msg = "Agendamiento actualizado correctamente."
            else:
                agenda = Agenda.objects.create(
                    actividad=actividad,
                    responsable=responsable,
                    fecha_inicio=f_ini,
                    fecha_fin=f_fin,
                    sede=sede,
                    color_hex=color_hex,
                    observacion=observacion,
                    created_by=user_auth,
                    updated_by=user_auth,
                )
                msg = "Agendamiento creado correctamente."

            # 1. Sincronizar estado en Actividad principal (si se especifica)
            # NOTA DE DOMINIO: El responsable de la actividad es el jefe creador de la OT y una actividad
            # puede vincularse a múltiples técnicos en la agenda. No se debe sobreescribir responsable_id
            # ni las fechas macro de la actividad en cada agendamiento individual.
            ESTADOS_VALIDOS_ACTIVIDAD = {
                "pendiente",
                "en_progreso",
                "completada",
                "cancelada",
                "pausada",
                "reprogramada",
                "agendado",
                "agendada",
            }
            nuevo_estado = data.get("estado") or (data_form.get("estado") if isinstance(data_form, dict) else None)
            if nuevo_estado and str(nuevo_estado).strip():
                estado_clean = str(nuevo_estado).strip().lower()
                if estado_clean in ESTADOS_VALIDOS_ACTIVIDAD:
                    if estado_clean == "agendada":
                        estado_clean = "agendado"
                    if actividad.estado != estado_clean:
                        actividad.estado = estado_clean
                        actividad.save(update_fields=["estado"])

            # 2. Sincronizar Detalle (operaciones_actividaddetalle)
            tipo_trabajo = data.get("tipo_trabajo") or (data_form.get("nombre_param") if isinstance(data_form, dict) else None)
            descripcion = data.get("descripcion") or (data_form.get("descripcion_actividad_param") if isinstance(data_form, dict) else None)
            if tipo_trabajo or descripcion:
                detalle = getattr(actividad, "detalle", None)
                if detalle:
                    if tipo_trabajo:
                        detalle.tipo_trabajo = str(tipo_trabajo).strip()
                    if descripcion:
                        detalle.descripcion = str(descripcion).strip()
                    detalle.save()
                else:
                    ActividadDetalle.objects.create(
                        actividad=actividad,
                        tipo_trabajo=str(tipo_trabajo or "").strip(),
                        descripcion=str(descripcion or "").strip(),
                    )

            # 3. Sincronizar Ubicación (operaciones_actividadubicacion)
            direccion = data.get("direccion") or (data_form.get("direccion_actividad_param") if isinstance(data_form, dict) else None)
            zona = data.get("zona") or (data_form.get("zona_actividad_param") if isinstance(data_form, dict) else None)
            nodo = data.get("nodo") or (data_form.get("nodo_actividad_param") if isinstance(data_form, dict) else None)
            longitud = data.get("longitud") or (data_form.get("longitud_param") if isinstance(data_form, dict) else None)
            latitud = data.get("latitud") or (data_form.get("latitud_param") if isinstance(data_form, dict) else None)

            if direccion is not None or zona is not None or nodo is not None or longitud is not None or latitud is not None:
                ubicacion = getattr(actividad, "ubicacion", None)
                if ubicacion:
                    if direccion is not None:
                        ubicacion.direccion = str(direccion).strip()
                    if zona is not None:
                        ubicacion.zona = str(zona).strip()
                    if nodo is not None:
                        ubicacion.nodo = str(nodo).strip()
                    if longitud is not None:
                        ubicacion.coordenada_x = str(longitud).strip()
                    if latitud is not None:
                        ubicacion.coordenada_y = str(latitud).strip()
                    ubicacion.save()
                else:
                    ActividadUbicacion.objects.create(
                        actividad=actividad,
                        direccion=str(direccion or "").strip(),
                        zona=str(zona or "").strip(),
                        nodo=str(nodo or "").strip(),
                        coordenada_x=str(longitud or "").strip(),
                        coordenada_y=str(latitud or "").strip(),
                    )

            # 4. Sincronizar Snapshot del Responsable (operaciones_actividadresponsablesnapshot)
            try:
                from apps.empleados.models.empleado_model import Empleado
                emp_obj = Empleado.objects.filter(cedula=responsable.username).first()
                nombre_resp = f"{emp_obj.nombre} {emp_obj.apellido}".strip() if emp_obj else (responsable.get_full_name().strip() or responsable.username)
                area_resp = (emp_obj.area if emp_obj else "") or data.get("area") or (data_form.get("area_agen") if isinstance(data_form, dict) else "") or ""
                carpeta_resp = (emp_obj.carpeta if emp_obj else "") or data.get("carpeta") or (data_form.get("carp_agen") if isinstance(data_form, dict) else "") or ""
                cargo_resp = (emp_obj.cargo if emp_obj else "") or ""
                movil_resp = (emp_obj.movil if emp_obj else "") or ""
                
                ActividadResponsableSnapshot.objects.update_or_create(
                    actividad=actividad,
                    defaults={
                        "empleado_id": emp_obj.id if emp_obj else responsable.id,
                        "nombre": nombre_resp,
                        "area": area_resp,
                        "carpeta": carpeta_resp,
                        "cargo": cargo_resp,
                        "movil": movil_resp,
                    }
                )
            except Exception:
                pass

        serialized = AgendaReadSerializer(agenda).data
        return {
            "success": True,
            "msg": msg,
            "data": serialized,
        }

    @staticmethod
    def eliminar_agenda(agenda_id: int, user: Optional[Any] = None) -> Dict[str, Any]:
        """
        Eliminación lógica (soft-delete) de un agendamiento.
        """
        agenda = Agenda.objects.filter(id=agenda_id, is_deleted=False).first()
        if not agenda:
            raise ValueError(f"No se encontró el agendamiento con ID {agenda_id}.")

        agenda.is_deleted = True
        agenda.deleted_at = timezone.now()
        if user and getattr(user, "is_authenticated", False):
            agenda.deleted_by = user
        agenda.save()

        return {
            "success": True,
            "msg": "Agendamiento eliminado correctamente.",
        }

    @staticmethod
    def importar_csv(file_obj: Any, user: Optional[Any] = None) -> Dict[str, Any]:
        """
        Importa registros masivos desde un archivo CSV a `operaciones_agenda`.
        Valida que cada OT exista, resuelve el técnico por cédula/ID y valida las fechas.
        """
        raw_bytes = file_obj.read()
        try:
            content = raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            content = raw_bytes.decode("latin-1")

        # Detectar delimitador (, o ;)
        sample = content[:2048]
        delimiter = ";" if ";" in sample and sample.count(";") > sample.count(",") else ","
        reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)

        resultados = []
        exitosos = 0
        fallidos = 0

        # Normalizar claves de encabezado a minúsculas y sin espacios
        for idx, raw_row in enumerate(reader, start=1):
            row = {str(k).strip().lower(): str(v).strip() for k, v in raw_row.items() if k is not None and v is not None}
            if not any(row.values()):
                continue

            ot = row.get("ot") or row.get("actividad") or row.get("orden_trabajo") or ""
            cedula = row.get("cedula") or row.get("cc") or row.get("identificacion") or row.get("tecnico") or ""
            responsable_id_raw = row.get("responsable_id") or row.get("tecnico_id")
            f_ini = row.get("fecha_inicio") or row.get("fecha_ini") or row.get("fecha") or row.get("inicio") or ""
            f_fin = row.get("fecha_fin") or row.get("fecha_final") or row.get("fin") or f_ini
            sede = (row.get("sede") or "medellin").lower()
            color = row.get("color_hex") or row.get("color") or "#A55BD8"
            nombre_act = row.get("nombre_actividad") or row.get("nombre") or ""

            try:
                if not ot:
                    raise ValueError("Falta el código de la OT.")
                if not f_ini:
                    raise ValueError("Falta la fecha de inicio.")

                # 1. Validar que la OT exista en el sistema de actividades
                act_info = AgendaService.buscar_actividad_por_ot(ot)
                if not act_info:
                    raise ValueError(f"La OT '{ot}' no existe en el módulo de actividades.")

                # 2. Resolver el técnico / responsable
                responsable_id = None
                tiene_identificador = bool(responsable_id_raw or cedula)

                if cedula:
                    u_obj = User.objects.filter(username=cedula, is_active=True).first()
                    if u_obj:
                        responsable_id = u_obj.id
                    else:
                        raise ValueError(f"El técnico con cédula '{cedula}' no existe o no se encuentra activo en el sistema.")
                elif responsable_id_raw and str(responsable_id_raw).isdigit():
                    responsable_id = int(responsable_id_raw)

                # Fallback al responsable de la OT únicamente si la fila no traía cédula ni responsable_id
                if not tiene_identificador:
                    responsable_id = act_info.get("responsable_id")

                if not responsable_id:
                    raise ValueError(f"No se pudo determinar un técnico responsable activo para la fila {idx}.")

                # 3. Guardar con transacción individual por fila
                with transaction.atomic():
                    AgendaService.save_agenda({
                        "actividad_id": act_info["id"],
                        "responsable_id": responsable_id,
                        "fecha_inicio": f_ini,
                        "fecha_fin": f_fin,
                        "sede": sede,
                        "color_hex": color,
                        "observacion": nombre_act or act_info.get("descripcion", ""),
                        "data_form": {
                            "actividad_id": act_info["id"],
                            "responsable_id": responsable_id,
                            "rad_sede_agen": sede,
                            "area_agen": act_info.get("responsable_area", ""),
                            "carp_agen": act_info.get("responsable_carpeta", ""),
                            "cc_agen_tecnico_search": cedula or "",
                            "actividad_param": ot.upper(),
                            "nombre_param": (nombre_act or act_info.get("tipo_trabajo", ot)).upper(),
                            "fec_agen_ini": f_ini,
                            "fec_agen_fin": f_fin,
                            "color_hex": color,
                        }
                    }, user=user)

                exitosos += 1
                resultados.append({
                    "fila": idx,
                    "cedula": cedula or str(responsable_id),
                    "ot": ot,
                    "fecha_inicio": f_ini,
                    "fecha_fin": f_fin,
                    "success": True,
                    "mensaje": "Agendado exitosamente.",
                })
            except Exception as e:
                fallidos += 1
                resultados.append({
                    "fila": idx,
                    "cedula": cedula or str(responsable_id_raw or ""),
                    "ot": ot or "N/A",
                    "fecha_inicio": f_ini or "N/A",
                    "fecha_fin": f_fin or "N/A",
                    "success": False,
                    "mensaje": str(e),
                })

        return {
            "success": True,
            "total_filas": len(resultados),
            "exitosos": exitosos,
            "fallidos": fallidos,
            "resultados": resultados,
            "msg": f"Se procesaron {len(resultados)} filas: {exitosos} exitosas y {fallidos} con error.",
        }
