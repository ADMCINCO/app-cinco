# Guia de Frontend (Next.js)

## Requisitos

- Node.js 18+ (LTS recomendado)
- npm 9+
- Next.js 16.4+ (App Router)
- React 19+

## Configuracion rapida

1. Ubicate en la carpeta `frontend`.
2. Instala dependencias:
   - `npm install`
3. Crea `.env.local` desde `.env.local.example`.

## Scripts principales

- Desarrollo: `npm run dev`
- Lint: `npm run lint`
- Typecheck: `npm run typecheck`
- Build: `npm run build`
- Produccion local: `npm run start`

## Integracion con backend

El frontend consume los endpoints de IA DEV, incluyendo:

- `POST /ia-dev/chat/`
- `POST /ia-dev/attendance/period/resolve/`
- `POST /ia-dev/memory/reset/`
- `GET /ia-dev/health/`
- `POST /ia-dev/tickets/`
- `POST /ia-dev/knowledge/proposals/`
- `GET /ia-dev/knowledge/proposals/`
- `POST /ia-dev/knowledge/proposals/approve/`
- `POST /ia-dev/knowledge/proposals/reject/`
- `GET /ia-dev/async/jobs/`
- `GET /ia-dev/observability/summary/`

## Estandar de texto y codificacion

- Mantener los textos en espanol latino y UTF-8.
- No usar texto corrupto (mojibake) en tildes, enes ni puntuacion.
- Validacion sugerida desde la raiz del repo:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\check_mojibake.ps1`
