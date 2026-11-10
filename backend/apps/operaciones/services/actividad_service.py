from typing import Optional
from django.db import transaction
from django.db.models import Q, Min, Max
from django.utils import timezone

from apps.empleados.services import EmpleadoService
from apps.operaciones.models import (
    Actividad,
    ActividadDetalle,
    ActividadOT,
    ActividadResponsableSnapshot,
    ActividadUbicacion,
    normalize_ot_values,
)


class ActividadService:
    @staticmethod
    def resolver_empleado_id_por_usuario(user) -> Optional[int]:
        """
        Resuelve el ID de empleado activo asociado a un usuario de autenticación.

        NOTA ARQUITECTÓNICA (Fase de Transición):
        Este método actúa como adapter temporal entre el modelo de autenticación (`auth_user`)
        y la base de personal legacy (`cinco_base_de_personal`) mientras se completa el desarrollo
        del nuevo módulo central de empleados y el sistema de roles y permisos (RBAC).

        Prioriza la búsqueda activa por cédula (username). Si no coincide, utiliza el
        ID de usuario únicamente cuando exista una asociación verificable (coincidencia
        por cédula, código SAP o correo electrónico), seleccionando exclusivamente el
        campo `id`. Si no existe asociación comprobable, no resuelve ningún empleado
        para evitar asignaciones erróneas.

        Args:
            user: Instancia de usuario de autenticación (django.contrib.auth.models.User).

        Returns:
            Optional[int]: ID del empleado activo o None si no se encuentra relación verificable.
        """
        if not user or not getattr(user, 'is_authenticated', False) or not getattr(user, 'is_active', False):
            return None

        from apps.empleados.models import Empleado

        username = getattr(user, 'username', None)
        clean_username = str(username).strip() if username else ""
        email = getattr(user, 'email', None)
        clean_email = str(email).strip().lower() if email else ""

        # 1. Prioridad: coincidencia activa por cédula
        if clean_username:
            emp_id = (
                Empleado.objects.filter(cedula=clean_username, estado="ACTIVO")
                .values_list('id', flat=True)
                .first()
            )
            if emp_id:
                return emp_id

        # 2. Fallback por ID: solo si existe una asociación verificable entre el empleado y el usuario
        user_id = getattr(user, 'id', None)
        if user_id:
            emp_data = (
                Empleado.objects.filter(id=user_id, estado="ACTIVO")
                .values('id', 'cedula', 'codigo_sap', 'correo', 'email_personal')
                .first()
            )
            if emp_data:
                cedula_val = str(emp_data.get('cedula') or '').strip().lower()
                sap_val = str(emp_data.get('codigo_sap') or '').strip().lower()
                correo_val = str(emp_data.get('correo') or '').strip().lower()
                personal_val = str(emp_data.get('email_personal') or '').strip().lower()

                es_verificable = False
                if clean_username and clean_username.lower() in (cedula_val, sap_val):
                    es_verificable = True
                elif clean_email and clean_email in (correo_val, personal_val):
                    es_verificable = True

                if es_verificable:
                    return emp_data['id']

        # 3. Compatibilidad con usuarios cuyo username corresponde a código SAP o correo
        if clean_username:
            emp_id = (
                Empleado.objects.filter(codigo_sap=clean_username, estado="ACTIVO")
                .values_list('id', flat=True)
                .first()
            )
            if emp_id:
                return emp_id

        if clean_email:
            from django.db.models import Q
            emp_id = (
                Empleado.objects.filter(
                    Q(correo__iexact=clean_email) | Q(email_personal__iexact=clean_email),
                    estado="ACTIVO",
                )
                .values_list('id', flat=True)
                .first()
            )
            if emp_id:
                return emp_id

        return None

    @staticmethod
    def resolver_usuario_por_empleado_id(empleado_id):
        """
        Resuelve el usuario de autenticación activo asociado a un empleado.

        Consulta directamente el registro del empleado activo y busca correspondencia
        con una cuenta de usuario activa (is_active=True) respetando la jerarquía de
        identificadores verificables: cédula, código SAP y correo corporativo o personal,
        en coherencia estricta con el contrato de resolver_empleado_id_por_usuario.

        Args:
            empleado_id: ID del empleado en la tabla de personal.

        Returns:
            Optional[User]: Instancia de User activo o None si no se encuentra relación verificable.
        """
        if not empleado_id:
            return None

        from apps.empleados.models import Empleado
        from django.contrib.auth import get_user_model

        User = get_user_model()

        emp = (
            Empleado.objects.filter(id=empleado_id, estado="ACTIVO")
            .values('id', 'cedula', 'codigo_sap', 'correo', 'email_personal', 'correo_electronico_personal')
            .first()
        )
        if not emp:
            return None

        cedula = str(emp.get('cedula') or '').strip()
        sap = str(emp.get('codigo_sap') or '').strip()
        correo = str(emp.get('correo') or '').strip()
        email_personal = str(emp.get('email_personal') or emp.get('correo_electronico_personal') or '').strip()

        # 1. Prioridad: coincidencia activa por cédula (username)
        if cedula:
            user = User.objects.filter(username=cedula, is_active=True).first()
            if user:
                return user

        # 2. Coincidencia por código SAP (username)
        if sap:
            user = User.objects.filter(username=sap, is_active=True).first()
            if user:
                return user

        # 3. Coincidencia por correo corporativo o personal
        if correo:
            user = User.objects.filter(email__iexact=correo, is_active=True).first()
            if user:
                return user

        if email_personal:
            user = User.objects.filter(email__iexact=email_personal, is_active=True).first()
            if user:
                return user

        return None

    @staticmethod
    def _sync_ots(actividad: Actividad, ots_data, actor_user_id=None):
        """
        Sincroniza las relaciones de Órdenes de Trabajo (OTs) asociadas a una actividad.

        Actualiza el código principal de la OT, activa o desactiva relaciones según los
        datos provistos y recalcula el rango de fechas macro de la actividad.

        Args:
            actividad: Instancia de Actividad a sincronizar.
            ots_data: Lista de diccionarios con la información de cada OT y sus fechas.
            actor_user_id: ID del usuario que ejecuta la sincronización.
        """
        # ots_data es una lista de diccionarios: [{'ot': '...', 'fecha_inicio': '...', 'fecha_fin': '...'}]
        # Extraemos los códigos de OT limpios
        ot_codes = [item['ot'].strip() for item in ots_data if item.get('ot')]
        actividad.ot = ot_codes[0] if ot_codes else ""
        actividad.save(update_fields=['ot', 'updated_at'])

        existing_relations = {
            relation.ot: relation
            for relation in ActividadOT.objects.filter(actividad=actividad)
        }

        current_active = set()
        for item in ots_data:
            ot = item.get('ot', '').strip()
            if not ot:
                continue

            fecha_inicio = item.get('fecha_inicio') or None
            fecha_fin = item.get('fecha_fin') or None

            relation = existing_relations.get(ot)
            if relation:
                updates = []
                if not relation.is_active:
                    relation.is_active = True
                    updates.append('is_active')
                if relation.fecha_inicio != fecha_inicio:
                    relation.fecha_inicio = fecha_inicio
                    updates.append('fecha_inicio')
                if relation.fecha_fin != fecha_fin:
                    relation.fecha_fin = fecha_fin
                    updates.append('fecha_fin')
                if actor_user_id is not None:
                    relation.updated_by = actor_user_id
                    updates.append('updated_by')
                if updates:
                    relation.save(update_fields=updates + ['updated_at'])
            else:
                ActividadOT.objects.create(
                    actividad=actividad,
                    ot=ot,
                    fecha_inicio=fecha_inicio,
                    fecha_fin=fecha_fin,
                    created_by=actor_user_id,
                    updated_by=actor_user_id,
                )
            current_active.add(ot)

        for ot, relation in existing_relations.items():
            if ot not in current_active and relation.is_active:
                relation.is_active = False
                relation.updated_by = actor_user_id
                relation.save(update_fields=['is_active', 'updated_by', 'updated_at'])

        # Recalcular fechas generales de la Actividad principal a partir de sus OTs activas
        relaciones_activas = ActividadOT.objects.filter(actividad=actividad, is_active=True)
        if relaciones_activas.exists():
            
            fechas = relaciones_activas.aggregate(
                min_inicio=Min('fecha_inicio'),
                max_fin=Max('fecha_fin')
            )
            actividad.fecha_inicio = fechas['min_inicio']
            actividad.fecha_fin_estimado = fechas['max_fin']
        else:
            actividad.fecha_inicio = None
            actividad.fecha_fin_estimado = None

        actividad.save(update_fields=['fecha_inicio', 'fecha_fin_estimado', 'updated_at'])

    @staticmethod
    def validar_ots_unicas(ots, actividad_id=None):
        """
        Valida que los códigos de OT suministrados no estén ya asignados a otra actividad activa.

        Args:
            ots: Lista o colección de códigos de OT a verificar.
            actividad_id: ID opcional de la actividad actual para excluirla de la verificación.

        Raises:
            ValueError: Si alguna de las OTs ya está asociada a otra actividad activa.
        """
        normalized_ots = normalize_ot_values(ots)
        if not normalized_ots:
            return

        queryset = ActividadOT.objects.filter(ot__in=normalized_ots, is_active=True)
        if actividad_id is not None:
            queryset = queryset.exclude(actividad_id=actividad_id)

        duplicates = list(queryset.values_list('ot', flat=True))
        if duplicates:
            duplicated = ", ".join(sorted(set(duplicates)))
            raise ValueError(
                f"Las siguientes OTs ya están asociadas a otra actividad: {duplicated}"
            )

    @staticmethod
    def crear(data: dict, actor_user_id=None) -> Actividad:
        """
        Crea una nueva Actividad junto con su detalle, ubicación, snapshot y relaciones de OTs.

        Normaliza el campo de estado a minúsculas y garantiza atomicidad transaccional.

        Args:
            data: Diccionario con la información completa de la actividad y entidades asociadas.
            actor_user_id: ID del usuario creador de la actividad.

        Returns:
            Actividad: La instancia recién creada y persistida en base de datos.

        Raises:
            ValueError: Si el responsable no existe o si las OTs están duplicadas.
        """
        payload = data.copy()
        detalle_data = payload.pop('detalle')
        ubicacion_data = payload.pop('ubicacion')
        ots = payload.pop('ots', None)
        payload.pop('ot', None)

        with transaction.atomic():
            responsable_id = payload.get('responsable_id')
            auth_responsable_id = None
            empleado = None

            if actor_user_id is not None:
                from django.contrib.auth import get_user_model
                actor_user = get_user_model().objects.filter(id=actor_user_id, is_active=True).first()
                if not actor_user:
                    raise ValueError("El usuario creador no existe o se encuentra inactivo en la plataforma.")

                empleado_perfil_id = ActividadService.resolver_empleado_id_por_usuario(actor_user)
                if not empleado_perfil_id:
                    raise ValueError(
                        "No se encontró un perfil de empleado activo asociado a tu usuario para asignarlo como responsable."
                    )
                if responsable_id and responsable_id != empleado_perfil_id:
                    raise ValueError(
                        "El responsable de la actividad no puede ser una persona diferente a la de tu perfil."
                    )
                empleado = EmpleadoService().obtener_basico(empleado_perfil_id)
                # Enlace relacional: Actividad.responsable apunta a auth_user activo (base para futuro RBAC)
                auth_responsable_id = actor_user.id

            if not empleado:
                if not responsable_id:
                    raise ValueError("El responsable de la actividad es obligatorio.")
                empleado = EmpleadoService().obtener_basico(responsable_id)
                if not empleado:
                    raise ValueError("El empleado responsable no existe o está inactivo.")

            if not auth_responsable_id:
                auth_user = ActividadService.resolver_usuario_por_empleado_id(empleado['id'])
                if auth_user:
                    auth_responsable_id = auth_user.id
                else:
                    raise ValueError("El empleado responsable no cuenta con un usuario de acceso activo en el sistema.")

            ot_codes = [item['ot'] for item in ots if item.get('ot')] if ots else []
            ActividadService.validar_ots_unicas(ot_codes)

            payload['responsable_id'] = auth_responsable_id
            if actor_user_id is not None:
                payload['created_by_id'] = actor_user_id
                payload['updated_by_id'] = actor_user_id
            payload['ot'] = ot_codes[0] if ot_codes else ""
            if payload.get('estado'):
                payload['estado'] = str(payload['estado']).strip().lower()

            actividad = Actividad.objects.create(**payload)

            ActividadResponsableSnapshot.objects.create(
                actividad=actividad,
                empleado_id=empleado['id'],
                nombre=empleado['nombre'],
                area=empleado.get('area') or "",
                carpeta=empleado.get('carpeta') or "",
                cargo=empleado.get('cargo') or "",
                movil=empleado.get('movil') or "",
            )

            ActividadUbicacion.objects.create(
                actividad=actividad,
                **ubicacion_data,
            )

            ActividadDetalle.objects.create(
                actividad=actividad,
                **detalle_data,
            )

            ActividadService._sync_ots(
                actividad,
                ots,
                actor_user_id=actor_user_id,
            )

            return actividad

    @staticmethod
    def actualizar(instance: Actividad, validated_data: dict, actor_user_id=None) -> Actividad:
        """
        Actualiza una Actividad existente y sus relaciones asociadas.

        Normaliza el estado a minúsculas y sincroniza detalle, ubicación y OTs según aplique.

        Args:
            instance: Instancia de Actividad a modificar.
            validated_data: Diccionario con los campos validados a actualizar.
            actor_user_id: ID del usuario que ejecuta la actualización.

        Returns:
            Actividad: La instancia actualizada.

        Raises:
            ValueError: Si el responsable asignado no existe o si las OTs entran en conflicto.
        """
        detalle_data = validated_data.pop('detalle', None)
        ubicacion_data = validated_data.pop('ubicacion', None)
        ots = validated_data.pop('ots', None)
        nuevo_emp_id = validated_data.pop('responsable_id', None)

        with transaction.atomic():
            if ots is not None:
                ot_codes = [item['ot'] for item in ots if item.get('ot')]
                ActividadService.validar_ots_unicas(ot_codes, actividad_id=instance.id)

            if nuevo_emp_id is not None:
                empleado = EmpleadoService().obtener_basico(nuevo_emp_id)
                if not empleado:
                    raise ValueError("El empleado responsable no existe o está inactivo.")

                auth_user = ActividadService.resolver_usuario_por_empleado_id(nuevo_emp_id)
                if not auth_user:
                    raise ValueError("El nuevo empleado responsable no cuenta con un usuario de acceso activo en el sistema.")

                instance.responsable = auth_user

                ActividadResponsableSnapshot.objects.update_or_create(
                    actividad=instance,
                    defaults={
                        'empleado_id': empleado['id'],
                        'nombre': empleado['nombre'],
                        'area': empleado.get('area') or "",
                        'carpeta': empleado.get('carpeta') or "",
                        'cargo': empleado.get('cargo') or "",
                        'movil': empleado.get('movil') or "",
                    },
                )

            if validated_data.get('estado'):
                validated_data['estado'] = str(validated_data['estado']).strip().lower()

            for field, value in validated_data.items():
                setattr(instance, field, value)

            if actor_user_id is not None:
                instance.updated_by_id = actor_user_id

            instance.save()

            if detalle_data:
                ActividadDetalle.objects.update_or_create(
                    actividad=instance,
                    defaults=detalle_data,
                )

            if ubicacion_data:
                ActividadUbicacion.objects.update_or_create(
                    actividad=instance,
                    defaults=ubicacion_data,
                )

            if ots is not None:
                ActividadService._sync_ots(
                    instance,
                    ots,
                    actor_user_id=actor_user_id,
                )

        return instance

    @staticmethod
    def listar(usuario_id=None, filtros=None, user=None):
        """
        Consulta y filtra las actividades activas del sistema.

        Aplica filtros avanzados (OT, estado insensible a mayúsculas, área, carpeta, búsqueda de texto)
        y precarga las relaciones necesarias para optimizar consultas.

        Args:
            usuario_id: ID opcional del usuario para filtrar actividades por asignación.
            filtros: Diccionario con parámetros opcionales de búsqueda y filtrado.
            user: Instancia opcional de autenticación para validar privilegios de supervisión y resolver empleado.

        Returns:
            QuerySet: Conjunto de actividades filtradas y optimizadas.
        """
        queryset = Actividad.objects.filter(is_deleted=False).select_related(
            'detalle',
            'ubicacion',
            'responsable_snapshot',
        ).prefetch_related('ot_relaciones')
        filtros = filtros or {}

        # Filtrado por usuario en sesión: Por defecto, restringe a las actividades creadas por el usuario
        # o vinculadas a su perfil de empleado. Solo si se solicita explícitamente `ver_todas=true`
        # y el usuario cuenta con permisos de staff/superuser, se desactiva el filtro.
        ver_todas = str(filtros.get('todas', '')).lower() in ('true', '1') or str(filtros.get('ver_todas', '')).lower() in ('true', '1')
        es_global = bool(ver_todas and user and (getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False)))

        if usuario_id and not es_global:
            empleado_perfil_id = None
            if user:
                empleado_perfil_id = ActividadService.resolver_empleado_id_por_usuario(user)
            elif usuario_id:
                from django.contrib.auth import get_user_model
                u = get_user_model().objects.filter(id=usuario_id).first()
                if u:
                    empleado_perfil_id = ActividadService.resolver_empleado_id_por_usuario(u)

            filtro_usuario = Q(created_by_id=usuario_id) | Q(responsable_id=usuario_id)
            if empleado_perfil_id:
                filtro_usuario |= Q(responsable_snapshot__empleado_id=empleado_perfil_id)

            queryset = queryset.filter(filtro_usuario).distinct()

        if filtros.get('ot'):
            queryset = queryset.filter(
                Q(ot__icontains=filtros['ot']) |
                Q(ot_relaciones__ot__icontains=filtros['ot'], ot_relaciones__is_active=True)
            ).distinct()

        if filtros.get('estado'):
            queryset = queryset.filter(estado__iexact=str(filtros['estado']).strip())

        if filtros.get('area'):
            queryset = queryset.filter(
                responsable_snapshot__area__icontains=filtros['area']
            )

        if filtros.get('carpeta'):
            queryset = queryset.filter(
                responsable_snapshot__carpeta__icontains=filtros['carpeta']
            )

        if filtros.get('buscar'):
            buscar = filtros['buscar']
            queryset = queryset.filter(
                Q(detalle__descripcion__icontains=buscar) |
                Q(detalle__tipo_trabajo__icontains=buscar) |
                Q(ot__icontains=buscar) |
                Q(ot_relaciones__ot__icontains=buscar, ot_relaciones__is_active=True) |
                Q(responsable_snapshot__nombre__icontains=buscar)
            ).distinct()

        if filtros.get('responsable_id'):
            queryset = queryset.filter(
                responsable_snapshot__empleado_id=filtros['responsable_id']
            )

        if filtros.get('fecha_inicio_desde'):
            queryset = queryset.filter(
                fecha_inicio__gte=filtros['fecha_inicio_desde']
            )

        if filtros.get('fecha_inicio_hasta'):
            queryset = queryset.filter(
                fecha_inicio__lte=filtros['fecha_inicio_hasta']
            )

        if filtros.get('zona'):
            queryset = queryset.filter(
                ubicacion__zona__icontains=filtros['zona']
            )

        if filtros.get('nodo'):
            queryset = queryset.filter(
                ubicacion__nodo__icontains=filtros['nodo']
            )

        return queryset

    @staticmethod
    def eliminar(instance: Actividad, actor_user=None, hard_delete=False) -> bool:
        """
        Elimina una actividad de forma lógica (soft delete) o física (hard delete).

        Args:
            instance: Instancia de Actividad a eliminar.
            actor_user: Usuario autenticado que solicita la eliminación.
            hard_delete: Booleano indicando si se debe borrar físicamente el registro (requiere superusuario).

        Returns:
            bool: True si la eliminación fue exitosa, False en caso contrario.
        """
        if hard_delete:
            if not actor_user or not actor_user.is_authenticated or not actor_user.is_superuser:
                return False
            instance.delete()
            return True

        deleted_by_id = actor_user.id if actor_user and actor_user.is_authenticated else None
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.deleted_by_id = deleted_by_id
        if deleted_by_id is not None:
            instance.updated_by_id = deleted_by_id
        instance.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by', 'updated_at'])
        return True
