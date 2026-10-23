# Guía de Contribución al Proyecto

¡Bienvenido! Este documento detalla las tecnologías requeridas, el paso a paso para configurar tu entorno local, el flujo de trabajo con Git y las reglas base para contribuir al proyecto.

---

## 🛠️ Tecnologías Requeridas

### General

- **Git:** Control de versiones.
- **PowerShell 7+** (Windows) o **Bash** (Linux/macOS).

### Backend (Django)

- **Python:** 3.11+ (Recomendado 3.11).
- **Framework:** Django 5.2.18+ & Django REST Framework 3.18.3+.
- **Autenticación:** `djangorestframework_simplejwt` (JWT) & `PyJWT` 2.15+.
- **Base de Datos:** MySQL / MariaDB (Driver `mysqlclient` 2.2+).
- **Documentación API:** `drf-spectacular` (OpenAPI 3.0).
- **Integraciones / IA:** `openai` API client, `python-dotenv` 1.2.4+, `requests` 2.34+, `reportlab`.
- **Caché y Mensajería (Opcional):** Redis 8+ (`redis-py`).

### Frontend (Next.js)

- **Entorno de Ejecución:** Node.js 18+ (LTS recomendado) y **npm 9+**.
- **Framework:** Next.js 16.4+ (App Router con parches de seguridad activos).
- **Biblioteca de Interfaz:** React 19+, TailwindCSS 4+, Radix UI / Shadcn UI, Lucide React.
- **Gestión de Estado y Formularios:** Zustand 5+, React Hook Form, Zod.
- **Visualización y Tablas:** ApexCharts, AmCharts 5, FullCalendar, TanStack Table, SheetJS XLSX (0.20+ CDN).
- **Calidad de Código y Formato:** TypeScript 5.9+, ESLint 9+, PostCSS 8.5.31+, Prettier, Husky & Lint-Staged.

---

## 🚀 Paso a Paso para Configurar el Entorno Local

### 1. Clonar el Repositorio

```bash
git clone https://github.com/cincosas/app-cinco.git
cd app-cinco
```

### 2. Configuración del Backend (Django)

1. Navega al directorio del backend:

   ```bash
   cd backend
   ```

2. Crea y activa el entorno virtual de Python:

   - **Windows (PowerShell):**

     ```powershell
     python -m venv .venv
     .\.venv\Scripts\activate
     ```

   - **Linux / macOS:**

     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. Instala las dependencias necesarias:

   ```bash
   pip install -r requirements.txt
   ```

4. Configura las variables de entorno:

   - Copia `.env.example` a `.env`:

     ```bash
     cp .env.example .env
     ```

   - Modifica el archivo `.env` configurando las credenciales de base de datos y llaves necesarias.

5. Ejecuta el servidor de desarrollo:

   ```bash
   python manage.py runserver 127.0.0.1:8000
   ```

   *(También puedes utilizar el wrapper de PowerShell: `powershell -ExecutionPolicy Bypass -File .\scripts\dj.ps1 runserver 127.0.0.1:8000`)*

### 3. Configuración del Frontend (Next.js)

1. En una nueva ventana o pestaña de terminal, navega a la carpeta frontend:

   ```bash
   cd frontend
   ```

2. Instala los paquetes y dependencias de Node:

   ```bash
   npm install
   ```

3. Configura las variables de entorno locales:

   - Copia `.env.local.example` a `.env.local`:

     ```bash
     cp .env.local.example .env.local
     ```

   - Asegúrate de definir la URL base de la API backend (ej. `NEXT_PUBLIC_API_URL=http://localhost:8000`).

4. Inicia el servidor de desarrollo:

   ```bash
   npm run dev
   ```

5. Accede a la aplicación en `http://localhost:3000`.

---

## 🌿 Flujo de Trabajo y Reglas de Git (Git Flow)

### Estructura de Ramas

- `main`: Rama de producción protegida. Solo acepta merges mediante Pull Requests originados exclusivamente en `develop`. No se permiten pushes directos.
- `develop`: Rama principal de desarrollo e integración.
- `feat/*`: Ramas secundarias para desarrollo de nuevas características (ej. `feat/ausentismo-filtro`).
- `fix/*`: Ramas secundarias para corrección de fallos (ej. `fix/error-login-jwt`).

### Orden Estricto de Merge

```text
feat/* o fix/*  ->  develop  ->  main
```

### Pasos para Abrir un Pull Request (PR)

1. Crea tu rama desde `develop`:

   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feat/mi-funcionalidad
   ```

2. Realiza tus cambios y verifica el funcionamiento localmente.

3. Ejecuta las verificaciones locales antes de hacer commit o enviar el PR:

   - **Frontend:** `npm run lint`, `npm run typecheck`, `npm run build`.
   - **Backend:** `python manage.py check`.
   - **Validación de Mojibake / Encodings:**

     ```powershell
     powershell -ExecutionPolicy Bypass -File .\scripts\check_mojibake.ps1
     ```

4. Sube tu rama al remoto y abre el PR:

   ```bash
   git push origin feat/mi-funcionalidad
   ```

   - Abre un PR con destino a **`develop`**.
   - Tras probar y aprobar en `develop`, se abrirá un PR desde **`develop`** hacia **`main`**.

---

## ⚠️ Reglas Base del Proyecto y Gobernanza

1. **Codificación:** Todos los archivos de código y documentación deben guardarse en formato **UTF-8** para prevenir texto corrupto (mojibake).
2. **Rutas e Integridad:** Prohibido modificar las rutas de controladores o endpoints preexistentes.
3. **Producción:** Prohibido ejecutar comandos DML/DDL invasivos (`INSERT`, `UPDATE`, `DELETE`, `ALTER`) directamente en la base de datos de producción sin autorización previa explícita.
4. **Gobernanza de Datos IA:** Toda tabla `ia_dev_*` debe residir y operar **únicamente** en el esquema `ai_dictionary` (nunca en `db_cincosas`).
5. **Comandos Django Restringidos:** No ejecutar `makemigrations` ni `migrate` sin autorización previa en ambientes controlados.
