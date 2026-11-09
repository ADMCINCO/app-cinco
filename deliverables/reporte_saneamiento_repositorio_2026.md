# Informe Técnico: Saneamiento de Repositorio, Limpieza de Código Muerto y Optimización de Dependencias

- **Fecha:** 2026-11-09
- **Rama:** `chore/saneamiento-repositorio-limpieza-dependencias`
- **Proyecto:** ADMCINCO (`app-cinco`)

---

## 1. Resumen Ejecutivo

En concordancia con las directrices de arquitectura y gobernanza del proyecto, se realizó una auditoría y saneamiento integral del repositorio. El objetivo principal fue depurar componentes redundantes o ficticios (código muerto de plantillas base), optimizar el árbol de dependencias, corregir reglas de `.gitignore` para prevenir fugas de archivos de depuración o binarios pesados, y asegurar la máxima velocidad y estabilidad tanto en el backend Django como en el frontend Next.js.

---

## 2. Ajustes Realizados en Backend (Django)

### 2.1 Optimización del Script de Sincronización Auth (`backend/scripts/sync_auth_users.py`)
- **Problema previo:** El script ejecutaba dos consultas a la base de datos por cada registro evaluado (para ~5.766 filas), resultando en tiempos de ejecución superiores a 10 minutos.
- **Solución implementada:** Se pre-cargaron en memoria los conjuntos (`sets`) de `existing_ids` y `existing_usernames`. La verificación de existencia ahora se realiza en complejidad \(O(1)\).
- **Resultado:** Tiempo de ejecución reducido a ~2 segundos, sincronizando con éxito 5.766 registros e importando 26 usuarios nuevos sin afectar el esquema relacional.

### 2.2 Saneamiento de Archivos y Reglas de Ignorado (`.gitignore`)
- **Creación de `backend/.gitignore`:** Se incorporaron reglas específicas para aislar entornos virtuales (`.venv/`, `env/`), bases SQLite locales (`db.sqlite3`), archivos temporales de exportación (`tmp/`, `*.csv`), logs de depuración (`debug_*.json`) y scripts scratch.
- **Actualización de `.gitignore` raíz:** Se excluyeron del control de versiones los archivos pesados comprimidos (`deliverables/*.zip`, `*.pptx`), mientras se preservó explícitamente el rastreo del archivo determinista `frontend/package-lock.json`.
- **Eliminación de archivos obsoletos / vacíos:**
  - `backend/apps/operaciones/models.py` (0 bytes, redundante).
  - `backend/apps/empleados/views.py` (plantilla vacía sin implementación).
  - `backend/debug_deco_fixed.json` y `backend/debug_deco_trace.json` (archivos de depuración locales).

### 2.3 Sincronización del Entorno Virtual Activo
- Se instalaron y validaron las dependencias requeridas en el entorno activo (`env/`): `openpyxl==3.1.5` y `msal==1.39.0`.

---

## 3. Ajustes Realizados en Frontend (Next.js)

### 3.1 Eliminación de Carpetas Duplicadas y Componentes Sombra
- **Módulo Operaciones / Actividad:** Se eliminó la subcarpeta redundante `frontend/src/modules/operaciones/actividad/ModalActividad/` (5 archivos), unificando el modal en su ubicación canónica `frontend/src/modules/operaciones/actividad/components/ModalActividad/`.

### 3.2 Eliminación de Stores y Servicios Huérfanos
- `frontend/src/store/empleado.store.ts`: Store no utilizado en la aplicación; los datos de empleados son gestionados a través de React Query / hooks de API.
- `frontend/src/store/menu.store.ts` y `frontend/src/services/menu.service.ts`: Código de menú dinámico no integrado ni consumido por `AppSidebar`.
- *Nota de Arquitectura:* El store principal de autenticación (`frontend/src/store/auth.store.ts`) permanece intacto y robusto, operando con cookies `httpOnly` seguras respaldadas por Django.

### 3.3 Remoción de Componentes Dummy de Demo
- **Tarjetas de Perfil:** Se eliminaron `UserInfoCard.tsx`, `UserAddressCard.tsx` y `UserMetaCard.tsx` en `frontend/src/components/user-profile/` (eran maquetas estáticas de plantilla sin datos reales).
- **Grids de Imágenes:** Se eliminaron `ResponsiveImage.tsx`, `ThreeColumnImageGrid.tsx` y `TwoColumnImageGrid.tsx` en `frontend/src/components/ui/images/`.

### 3.4 Optimización de Dependencias (`package.json` y `package-lock.json`)
- Se removieron dependencias no utilizadas en producción:
  - `@react-jvectormap/core` y `@react-jvectormap/world` (~2.5 MB).
  - `swiper` (~1.8 MB).
  - `react-dnd` y `react-dnd-html5-backend` (~1.2 MB).
- Se eliminó el bloque obsoleto `overrides` en `package.json`.
- Se ejecutó `npm install` podando 15 paquetes innecesarios del árbol de `node_modules` y actualizando `package-lock.json`.

### 3.5 Limpieza de Estilos y Navegación
- **`src/app/globals.css`:** Se removieron clases CSS de librerías externas eliminadas (Swiper y vector maps).
- **`src/components/layout/AppSidebar.tsx`:** Se eliminó el grupo muerto `othersItems` del menú lateral.
- **`src/app/(public)/login/page.tsx`:** Se corrigió el título de la pestaña de autenticación a "Iniciar Sesión - CINCO SAS".
- **Assets Gráficos:** Se eliminaron 51 imágenes y SVGs de plantilla en `frontend/public/images/` (`brand/`, `cards/`, `carousel/`, `chat/`, `country/`, `product/`, `task/`, `video-thumb/`, `grid-image/`).

---

## 4. Verificaciones y Pruebas de Calidad

| Capa | Comando / Prueba | Resultado |
| :--- | :--- | :--- |
| **Backend** | `python manage.py check` | 0 errores detectados |
| **Backend Tests** | `python manage.py test apps.empleados.tests` | 18/18 pruebas exitosas (100% OK) |
| **Frontend Tipos** | `npm run typecheck` | 0 errores de TypeScript |
| **Frontend Build** | `npm run build` | Compilación de producción exitosa (10/10 rutas generadas) |
| **Codificación** | Formato UTF-8 sin BOM verificado | Sin riesgo de Mojibake |

---

## 5. Impacto

1. **Rendimiento de Build y Bundle Size:**
   - Reducción considerable en el tamaño de los artefactos compilados del cliente y el árbol de dependencias (`node_modules`), acelerando los tiempos de CI/CD.
2. **Higiene del Repositorio:**
   - Eliminación de archivos temporales pesados y aislamiento de entornos virtuales locales.
   - Prevención de desincronizaciones entre desarrolladores gracias a la inclusión formal de `package-lock.json` y dependencias limpias.
3. **Mantenibilidad:**
   - Menos ruido cognitivo al navegar el código fuente, eliminando código muerto y maquetas que no interactuaban con la API de CINCO SAS.
