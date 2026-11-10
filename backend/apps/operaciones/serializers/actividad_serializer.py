from rest_framework import serializers
from apps.operaciones.models import (
    Actividad,
    ActividadDetalle,
    ActividadOT,
    ActividadUbicacion,
    normalize_ot_values,
)
from apps.empleados.services import EmpleadoService
from apps.operaciones.services.actividad_service import ActividadService


class OptionalDateField(serializers.DateField):
    """
    Campo de fecha flexible que acepta valores vacíos o nulos comunes en frontend.
    """

    def to_internal_value(self, value):
        """
        Convierte y normaliza cadenas vacías o representaciones de nulo a None.

        Args:
            value: Valor entrante que representa una fecha.

        Returns:
            date | None: Fecha parseada o None si el valor está vacío.
        """
        if isinstance(value, str):
            value = value.strip()
        if value in ("", None, "null", "undefined"):
            return None
        return super().to_internal_value(value)



class ActividadDetalleSerializer(serializers.ModelSerializer):
    descripcion = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = ActividadDetalle
        exclude = ('actividad',)


class ActividadUbicacionSerializer(serializers.ModelSerializer):
    coordenada_x = serializers.CharField(required=False, allow_blank=True)
    coordenada_y = serializers.CharField(required=False, allow_blank=True)
    zona = serializers.CharField(required=False, allow_blank=True)
    nodo = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = ActividadUbicacion
        exclude = ('actividad',)


class ActividadOTSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActividadOT
        fields = (
            'id',
            'ot',
            'fecha_inicio',
            'fecha_fin',
            'is_active',
            'created_at',
            'created_by',
            'updated_at',
            'updated_by',
        )


class ActividadOTWriteSerializer(serializers.Serializer):
    ot = serializers.CharField(max_length=100)
    fecha_inicio = OptionalDateField(
        input_formats=["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"],
        required=False,
        allow_null=True
    )
    fecha_fin = OptionalDateField(
        input_formats=["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"],
        required=False,
        allow_null=True
    )


class ActividadWriteSerializer(serializers.ModelSerializer):
    responsable_id = serializers.IntegerField(required=False)
    detalle = ActividadDetalleSerializer()
    ubicacion = ActividadUbicacionSerializer()
    ots = ActividadOTWriteSerializer(many=True, required=True)
    ot = serializers.CharField(required=False, allow_blank=False, write_only=True)
    
    # fecha_inicio = serializers.DateTimeField(
    #      input_formats=[
    #         "%Y-%m-%d",
    #         "%Y-%m-%dT%H:%M:%S",
    #         "%Y-%m-%dT%H:%M",
    #     ]
    # )
    
    # fecha_fin_estimado = serializers.DateTimeField(
    #     input_formats=[
    #         "%Y-%m-%d",
    #         "%Y-%m-%dT%H:%M:%S",
    #         "%Y-%m-%dT%H:%M",
    #     ]
    # )

    fecha_fin_real = OptionalDateField(
        input_formats=[
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M",
        ],
        required=False,
        allow_null=True
    )

    class Meta:
        model = Actividad
        fields = (
            'ot',
            'ots',
            'estado',
            'responsable_id',
            'fecha_inicio',
            'fecha_fin_estimado',
            'fecha_fin_real',
            'detalle',
            'ubicacion'
        )

    def to_internal_value(self, data):
        """
        Preprocesa y normaliza los datos de entrada antes de la validación del serializer.

        Convierte el campo estado a minúsculas para asegurar consistencia con los choices del modelo.

        Args:
            data: Diccionario de datos crudos enviados en la solicitud.

        Returns:
            dict: Diccionario procesado con tipos internos validados.
        """
        if isinstance(data, dict) and 'estado' in data and isinstance(data['estado'], str):
            data = data.copy()
            data['estado'] = data['estado'].strip().lower()
        return super().to_internal_value(data)

    def validate_responsable_id(self, value):
        """
        Valida que el empleado responsable exista, esté activo en la plataforma y, en creación, coincida con el perfil autenticado.

        Args:
            value: ID del empleado asignado como responsable.

        Returns:
            int: ID validado del empleado.

        Raises:
            serializers.ValidationError: Si el empleado no existe, no está activo o no coincide con el creador.
        """
        request = self.context.get('request')
        if self.instance is None and request and getattr(request, 'user', None) and request.user.is_authenticated:
            if not getattr(request.user, 'is_active', False):
                raise serializers.ValidationError("El usuario autenticado se encuentra inactivo.")
            empleado_perfil_id = ActividadService.resolver_empleado_id_por_usuario(request.user)
            if not empleado_perfil_id:
                raise serializers.ValidationError(
                    "No se encontró un perfil de empleado activo asociado a tu usuario para asignarlo como responsable."
                )
            if value != empleado_perfil_id:
                raise serializers.ValidationError(
                    "El responsable de la actividad no puede ser otra persona diferente a la de tu perfil."
                )

        if not EmpleadoService().existe(value):
            raise serializers.ValidationError("El empleado no existe o no está activo.")

        auth_user = ActividadService.resolver_usuario_por_empleado_id(value)
        if not auth_user:
            raise serializers.ValidationError(
                "El empleado responsable debe contar con un usuario de acceso activo en la plataforma."
            )

        return value

    def validate(self, attrs):
        ot = attrs.pop('ot', None)
        ots = attrs.get('ots')
        fecha_inicio = attrs.get('fecha_inicio')
        fecha_fin_estimado = attrs.get('fecha_fin_estimado')

        ot_codes = [item['ot'].strip() for item in ots if item.get('ot')] if ots else []
        
        normalized_ots = normalize_ot_values(ot_codes)
        if not normalized_ots:
            raise serializers.ValidationError(
                {"ots": "Debe registrar al menos una OT relacionada."}
            )

        try:
            ActividadService.validar_ots_unicas(
                normalized_ots,
                actividad_id=self.instance.id if self.instance else None,
            )
        except ValueError as exc:
            raise serializers.ValidationError({"ots": str(exc)}) from exc

        # Limpiar espacios de los códigos en attrs
        for item in ots:
            item['ot'] = item['ot'].strip()
            fecha_inicio_ot = item.get('fecha_inicio')
            fecha_fin_ot = item.get('fecha_fin')
            if (
                fecha_inicio_ot is not None and
                fecha_fin_ot is not None and
                fecha_fin_ot < fecha_inicio_ot
            ):
                raise serializers.ValidationError({
                    "ots": (
                        f"La OT {item['ot']} tiene una fecha fin menor que la fecha inicio."
                    )
                })

        if (
            fecha_inicio is not None and
            fecha_fin_estimado is not None and
            fecha_fin_estimado < fecha_inicio
        ):
            raise serializers.ValidationError({
                "fecha_fin_estimado": (
                    "La fecha fin estimada no puede ser menor que la fecha inicio."
                )
            })

        attrs['ots'] = ots
        return attrs

    def update(self, instance, validated_data):
        actor_user_id = self.context.get('actor_user_id')
        return ActividadService.actualizar(
            instance,
            validated_data,
            actor_user_id=actor_user_id,
        )

class ActividadSerializer(serializers.ModelSerializer):
    responsable_id = serializers.IntegerField(read_only=True)
    detalle = ActividadDetalleSerializer(read_only=True)
    ubicacion = ActividadUbicacionSerializer(read_only=True)
    responsable_snapshot = serializers.SerializerMethodField()
    ots = serializers.SerializerMethodField()
    ot_items = serializers.SerializerMethodField()

    class Meta:
        model = Actividad
        fields = "__all__"

    def to_representation(self, instance):
        """
        Transforma la instancia del modelo en representación serializada para respuesta API.

        Garantiza que el campo estado se entregue normalizado en minúsculas.

        Args:
            instance: Instancia de Actividad a serializar.

        Returns:
            dict: Representación serializada del registro.
        """
        data = super().to_representation(instance)
        if data.get('estado'):
            data['estado'] = str(data['estado']).strip().lower()
        return data

    def get_responsable_snapshot(self, obj):
        if hasattr(obj, 'responsable_snapshot'):
            return {
                "empleado_id": obj.responsable_snapshot.empleado_id,
                "nombre": obj.responsable_snapshot.nombre,
                "area": obj.responsable_snapshot.area,
                "carpeta": obj.responsable_snapshot.carpeta,
                "cargo": obj.responsable_snapshot.cargo,
                "movil": obj.responsable_snapshot.movil,
            }
        return None

    def get_ots(self, obj):
        return obj.ots_list

    def get_ot_items(self, obj):
        prefetched = getattr(obj, '_prefetched_objects_cache', {}).get('ot_relaciones')
        if prefetched is not None:
            relaciones = [relation for relation in prefetched if relation.is_active]
        else:
            relaciones = obj.ot_relaciones.filter(is_active=True)
        return ActividadOTSerializer(relaciones, many=True).data
