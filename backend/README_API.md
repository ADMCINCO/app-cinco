# 📚 API REST - App Cinco Backend

## 🚀 Descripción General

**App Cinco** es una API REST construida con Django y Django REST Framework que proporciona funcionalidades para:
- ✅ Autenticación y autorización
- ✅ Gestión de empleados
- ✅ Gestión de actividades/solicitudes
- ✅ Sistema de menús dinámicos basado en permisos
- ✅ Health checks y monitoreo

**Versión:** 1.0.0  
**Ambiente:** Django 5.2.18 | DRF 3.18.3 | Python 3.11+

---

## 📍 Acceso a Documentación

### Swagger UI (Recomendado)
```
http://127.0.0.1:8000/api/docs/
```
- Interfaz visual e interactiva
- Prueba de endpoints directa
- Autorización integrada

### ReDoc
```
http://127.0.0.1:8000/api/redoc/
```
- Documentación limpia y organizada
- Lectura únicamente

### OpenAPI Schema (JSON)
```
http://127.0.0.1:8000/api/schema/
```
- Esquema completo en formato JSON
- Importable en Postman, Insomnia, etc.

---

## 🔐 Autenticación

### Métodos Soportados
1. **Bearer Token (JWT)**
   ```
   Authorization: Bearer <access_token>
   ```

2. **API Key** (si está configurada)
   ```
   Authorization: ApiKey <api_key>
   ```

### Flujo de Autenticación
```
1. POST /auth/login/           → Obtener access_token y refresh_token
2. GET /auth/csrf/             → Obtener CSRF token (para frontend)
3. GET /auth/health/           → Verificar estado del servidor
4. POST /auth/refresh/         → Renovar access_token
5. POST /auth/logout/          → Cerrar sesión (revocar tokens)
```

---

## 📡 Endpoints por Módulo

### 🔑 **Autenticación** (`/auth/`)

#### 1. **POST /auth/login/** - Iniciar sesión
Autentica usuario con credenciales y genera tokens.

**Body:**
```json
{
  "username": "usuario",
  "password": "contraseña"
}
```

**Respuesta (200):**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": 1,
    "username": "usuario",
    "email": "usuario@example.com"
  }
}
```

**Errores:**
- `400`: Usuario y contraseña requeridos
- `401`: Credenciales inválidas

---

#### 2. **POST /auth/refresh/** - Renovar token
Genera un nuevo access_token usando el refresh_token.

**Body:**
```json
{
  "refresh": "refresh_token_aqui"
}
```

**Respuesta (200):**
```json
{
  "access_token": "nuevo_token_aqui",
  "refresh_token": "nuevo_refresh_aqui"
}
```

---

#### 3. **POST /auth/logout/** - Cerrar sesión
Revoca tokens y limpia cookies de autenticación.

**Respuesta (200):**
```json
{
  "detail": "Logout successful"
}
```

---

#### 4. **GET /auth/csrf/** - Obtener CSRF Token
Establece cookie CSRF para el frontend.

**Respuesta (200):**
```json
{
  "detail": "CSRF cookie set"
}
```

---

#### 5. **GET /auth/health/** - Health Check
Verifica el estado del servidor y conexiones a bases de datos.

**Respuesta (200):**
```json
{
  "status": "healthy",
  "service": "app-cinco-backend",
  "databases": {
    "default": "connected",
    "azul": "connected"
  }
}
```

**Respuesta (503):**
```json
{
  "status": "unhealthy",
  "service": "app-cinco-backend",
  "error": "Database connection failed"
}
```

---

### 👔 **Empleados** (`/empleados/empleados/`)

#### 1. **GET /empleados/empleados/** - Listar empleados
Obtiene listado de empleados activos con búsqueda.

**Parámetros:**
- `search`: Búsqueda parcial en cédula, nombre, apellido, cargo, móvil
- `page`: Número de página (paginación)
- Pagination`: Resultados por página

**Ejemplo:**
```bash
GET /empleados/empleados/?search=juan
GET /empleados/empleados/?search=3001234567
```

**Respuesta (200):**
```json
{
  "count": 45,
  "next": "http://127.0.0.1:8000/empleados/empleados/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "cedula": "1234567890",
      "nombre": "Juan",
      "apellido": "Pérez",
      "area": "Soporte Técnico",
      "carpeta": "Carpeta A",
      "cargo": "Técnico Senior",
      "movil": "3001234567",
      "estado": "ACTIVO"
    }
  ]
}
```

---

#### 2. **POST /empleados/empleados/** - Crear empleado
Crea un nuevo empleado.

**Body:**
```json
{
  "cedula": "1234567890",
  "nombre": "Carlos",
  "apellido": "Gómez",
  "area": "Instalación",
  "carpeta": "Carpeta B",
  "cargo": "Técnico",
  "movil": "3001234567",
  "estado": "ACTIVO"
}
```

**Respuesta (201):**
```json
{
  "id": 2,
  "cedula": "1234567890",
  "nombre": "Carlos",
  "apellido": "Gómez",
  "area": "Instalación",
  "carpeta": "Carpeta B",
  "cargo": "Técnico",
  "movil": "3001234567",
  "estado": "ACTIVO"
}
```

**Errores:**
- `400`: Datos inválidos
- `409`: Cédula duplicada

---

#### 3. **GET /empleados/empleados/{id}/** - Obtener detalles
Obtiene información completa de un empleado.

---

#### 4. **PUT /empleados/empleados/{id}/** - Actualizar completamente
Actualiza todos los campos del empleado.

---

#### 5. **PATCH /empleados/empleados/{id}/** - Actualizar parcialmente
Actualiza solo los campos proporcionados.

---

#### 6. **DELETE /empleados/empleados/{id}/** - Eliminar empleado
Elimina un empleado.

---

### 📋 **Actividades** (`/operaciones/actividades/`)

#### 1. **GET /operaciones/actividades/** - Listar actividades

**Filtrado automático por perfil:**
- Solo muestra actividades que creaste o donde eres responsable

**Parámetros de filtrado:**
- `ot`: Orden de Trabajo (búsqueda parcial)
- `estado`: Estado (pendiente, en_progreso, completada, cancelada, pausada, reprogramada)
- `area`: Área del responsable
- `carpeta`: Carpeta del responsable
- `responsable_id`: ID del empleado responsable
- `buscar`: Búsqueda general (descripción, tipo de trabajo, OT, nombre)
- `zona`: Zona de ubicación
- `nodo`: Nodo de ubicación
- `fecha_inicio_desde`: Fecha mínima (YYYY-MM-DD)
- `fecha_inicio_hasta`: Fecha máxima (YYYY-MM-DD)

**Ejemplos:**
```bash
GET /operaciones/actividades/
GET /operaciones/actividades/?estado=en_progreso
GET /operaciones/actividades/?area=Soporte&estado=pendiente
GET /operaciones/actividades/?buscar=instalación&zona=norte
GET /operaciones/actividades/?fecha_inicio_desde=2024-01-15&fecha_inicio_hasta=2024-02-15
```

**Respuesta (200):**
```json
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "ot": "OT-2024-001",
      "estado": "en_progreso",
      "responsable_id": 123,
      "fecha_inicio": "2024-01-15",
      "fecha_fin_estimado": "2024-01-20",
      "fecha_fin_real": null,
      "created_by": 456,
      "created_at": "2024-01-10T10:00:00Z",
      "detalle": {
        "tipo_trabajo": "Instalación",
        "descripcion": "Instalación de fibra óptica"
      },
      "ubicacion": {
        "direccion": "Calle Principal 123",
        "coordenada_x": "-75.5000",
        "coordenada_y": "10.4000",
        "zona": "norte",
        "nodo": "nodo-centro"
      },
      "responsable_snapshot": {
        "nombre": "Juan Pérez",
        "area": "Soporte Técnico",
        "carpeta": "Carpeta A",
        "cargo": "Técnico Senior",
        "movil": "3001234567"
      }
    }
  ]
}
```

---

#### 2. **POST /operaciones/actividades/** - Crear actividad

**Body:**
```json
{
  "ot": "OT-2024-001",
  "responsable_id": 123,
  "fecha_inicio": "2024-01-15",
  "fecha_fin_estimado": "2024-01-20",
  "detalle": {
    "tipo_trabajo": "Instalación",
    "descripcion": "Instalación de fibra óptica",
    "extra": {}
  },
  "ubicacion": {
    "direccion": "Calle Principal 123",
    "coordenada_x": "-75.5000",
    "coordenada_y": "10.4000",
    "zona": "norte",
    "nodo": "nodo-centro"
  }
}
```

**Respuesta (201):**
```json
{
  "id": 1,
  "ot": "OT-2024-001",
  "estado": "pendiente",
  ...
}
```

---

#### 3. **GET /operaciones/actividades/{id}/** - Obtener detalles

---

#### 4. **PUT /operaciones/actividades/{id}/** - Actualizar completamente

---

#### 5. **PATCH /operaciones/actividades/{id}/** - Actualizar parcialmente

**Ejemplo:** Cambiar estado a completado
```json
{
  "estado": "completada",
  "fecha_fin_real": "2024-01-20"
}
```

---

#### 6. **DELETE /operaciones/actividades/{id}/** - Eliminar actividad

---

### 🔐 **Security** (`/security/`)

#### 1. **GET /security/menu/** - Obtener menú del usuario

Retorna el menú dinámico según los permisos del usuario autenticado.

**Respuesta (200):**
```json
{
  "menu": [
    {
      "id": 1,
      "nombre": "Operaciones",
      "icono": "operations",
      "url": "/operaciones",
      "permisos": ["operaciones.view"],
      "submenu": [
        {
          "id": 2,
          "nombre": "Actividades",
          "url": "/operaciones/actividades"
        }
      ]
    }
  ]
}
```

**Errores:**
- `401`: No autenticado
- `403`: Sin permisos

---

## 📊 Códigos de Respuesta HTTP

| Código | Significado | Cuando |
|--------|-------------|--------|
| `200` | OK | Solicitud exitosa |
| `201` | Created | Recurso creado exitosamente |
| `204` | No Content | Eliminado exitosamente |
| `400` | Bad Request | Datos inválidos |
| `401` | Unauthorized | Falta autenticación |
| `403` | Forbidden | Sin permisos |
| `404` | Not Found | Recurso no existe |
| `409` | Conflict | Duplicado (ej: OT única) |
| `500` | Server Error | Error del servidor |
| `503` | Service Unavailable | Servicio no disponible |

---

## 🔄 Flujos Comunes

### Flujo de Login
```
1. POST /auth/login/ con username/password
   ↓
2. Recibir access_token + refresh_token
   ↓
3. Usar access_token en Authorization header
   ↓
4. (Opcional) GET /auth/csrf/ para obtener CSRF token
```

### Flujo de Renovación de Token
```
1. access_token expira
   ↓
2. POST /auth/refresh/ con refresh_token
   ↓
3. Recibir nuevo access_token
   ↓
4. Continuar usando nuevo token
```

### Flujo de Creación de Actividad
```
1. GET /operaciones/actividades/?responsable_id=123
   (para verificar empleado disponible)
   ↓
2. POST /operaciones/actividades/ con datos
   ↓
3. Recibir actividad creada con ID
   ↓
4. Usar ID para obtener detalles o actualizar
```

### Flujo de Búsqueda de Empleados
```
1. GET /empleados/empleados/?search=juan
   ↓
2. Recibir lista de empleados que coincidan
   ↓
3. (Opcional) GET /empleados/empleados/123/ para más detalles
```

---

## 🧪 Testing

### Herramientas Recomendadas

#### 1. Swagger UI (Navegador)
- Directo: `http://127.0.0.1:8000/api/docs/`
- Click "Authorize"
- Pega token
- Click "Try it out"

#### 2. Postman / Insomnia
```bash
1. Importar desde: http://127.0.0.1:8000/api/schema/
2. Configurar Bearer Token
3. Probar endpoints
```

#### 3. cURL
```bash
curl -X GET "http://127.0.0.1:8000/auth/login/" \
  -H "Authorization: Bearer <token>"
```

#### 4. Python
```python
import requests

headers = {
    "Authorization": "Bearer <token>"
}
response = requests.get(
    "http://127.0.0.1:8000/operaciones/actividades/",
    headers=headers,
    params={"estado": "en_progreso"}
)
print(response.json())
```

#### 5. JavaScript
```javascript
const token = "tu_token";
fetch("http://127.0.0.1:8000/operaciones/actividades/?estado=en_progreso", {
    headers: {
        "Authorization": `Bearer ${token}`
    }
})
.then(res => res.json())
.then(data => console.log(data));
```

---

## 📊 Datos de Ejemplo

### Estados de Actividad
```
- pendiente         → No iniciada
- en_progreso       → En ejecución
- completada        → Finalizada
- cancelada         → Cancelada
- pausada           → En pausa
- reprogramada      → Reprogramada
```

### Estados de Empleado
```
- ACTIVO            → Empleado activo
- INACTIVO          → Empleado inactivo (no aparece en búsquedas)
- LICENCIA          → En licencia
```

---

## 🔒 Seguridad y Notas Importantes

1. **CSRF Protection**: Frontend debe obtener CSRF token de `/auth/csrf/`
2. **Token Expiry**: Access tokens expiran, usar `/auth/refresh/` para renovar
3. **Soft Delete**: Actividades eliminadas se marcan *is_deleted=true* pero no se borran
4. **Snapshot**: Datos del responsable (nombre, área, etc.) se congelan al crear actividad
5. **Filtrado por Perfil**: Automático en actividades, solo ves tus datos
6. **Búsqueda Insensible**: Todos los filtros de texto ignoran mayúsculas/minúsculas
7. **Rate Limiting**: Puede estar configurado según ambiente

---

## 📚 Documentación Detallada por Módulo

- [ACTIVIDADES](./apps/operaciones/SWAGGER_DOCUMENTATION.md) - Guía de actividades
- [FILTRADO DE ACTIVIDADES](./apps/operaciones/FILTRADO_ACTIVIDADES.md) - Parámetros de filtro
- [REFERENCIA API REST](./apps/operaciones/API_REST_REFERENCE.md) - Referencia completa
- [ÍNDICE DE DOCS](./apps/operaciones/README_DOCS.md) - Documentación general

---

## ⚙️ Instalación y Setup

### Requerimientos
```
Django==5.2.18
djangorestframework==3.18.3
djangorestframework_simplejwt==5.5.1
drf-spectacular==0.29.0
mysqlclient==2.2.7
python-dotenv==1.2.4
PyJWT==2.15.1
redis==8.1.0
requests==2.34.2
urllib3==2.8.0
sqlparse==0.6.0
certifi==2026.10.23
idna==3.20
```

### Instalación
```bash
# Clonar repositorio
git clone <repo>

# Crear entorno virtual
python -m venv env
source env/Scripts/activate  # Windows

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar migraciones
python manage.py migrate

# Crear superusuario
python manage.py createsuperuser

# Correr servidor
python manage.py runserver
```

### Acceder a API
```
http://127.0.0.1:8000/api/docs/
```

---

## 📞 Soporte

En caso de problemas:
1. Verifica que el servidor esté corriendo: `py manage.py runserver`
2. Verifica el token Bearer en `Authorization` header
3. Revisa logs en terminal del servidor
4. Consulta Swagger UI en `/api/docs/` para ejemplos
5. Verifica CORS si vienen errores del frontend

---

## ✅ Checklist de Funcionalidades

- ✅ Autenticación JWT
- ✅ Refresh token rotation
- ✅ CSRF protection
- ✅ Health check
- ✅ Gestión de empleados
- ✅ Gestión de actividades
- ✅ Filtrado avanzado
- ✅ Búsqueda general
- ✅ Menú dinámico
- ✅ Documentación OpenAPI 3.0
- ✅ Soft delete
- ✅ Snapshot pattern

---

**Última actualización:** 4 de marzo de 2026  
**Versión API:** 1.0

