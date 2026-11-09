import csv
import os
import argparse
import sys
import re
from pathlib import Path

import django


def setup_django() -> None:
    """Configura el entorno y carga las configuraciones de Django para el script."""
    base_dir = Path(__file__).resolve().parents[1]
    if str(base_dir) not in sys.path:
        sys.path.insert(0, str(base_dir))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()


def normalize_text(value) -> str:
    """Normaliza un valor a cadena de texto limpia sin espacios iniciales o finales."""
    if value is None:
        return ""
    return str(value).strip()


def is_active_from_estado(estado: str) -> bool:
    """Determina si el estado recibido corresponde a un usuario activo."""
    return normalize_text(estado).upper() == "ACTIVO"


def is_identity_conflict(error, vendor: str) -> bool:
    """Identifica si el error de integridad corresponde exclusivamente a colisión de ID o username."""
    cause = error.__cause__
    if vendor == "mysql" and cause and len(cause.args) >= 2 and cause.args[0] == 1062:
        match = re.search(r"for key ['`]([^'`]+)['`]$", str(cause.args[1]))
        return bool(match and match.group(1).split(".")[-1] in {"PRIMARY", "username"})
    if vendor == "sqlite" and cause:
        return str(cause) in {
            "UNIQUE constraint failed: auth_user.id",
            "UNIQUE constraint failed: auth_user.username",
        }
    return False


def get_total_rows() -> int:
    """Obtiene el número total de registros en la tabla cinco_base_de_personal de la base 'azul'."""
    from django.db import connections
    with connections["azul"].cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM cinco_base_de_personal")
        row = cursor.fetchone()
        return row[0] if row else 0


def build_parser() -> argparse.ArgumentParser:
    """Construye y configura el parser de argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description=(
            "Carga usuarios en auth_user desde la tabla cinco_base_de_personal en la DB 'azul'."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula la carga sin escribir en la base de datos.",
    )
    parser.add_argument(
        "--output",
        default=str(Path("tmp") / "auth_user_import.csv"),
        help="Ruta del CSV donde se guardan usuarios nuevos y su password temporal.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Cantidad de registros por lote.",
    )
    return parser


def fetch_source_rows(batch_size: int):
    """Generador que obtiene registros de la base 'azul' por lotes para optimizar consumo de memoria."""
    from django.db import connections

    query = (
        "SELECT id, cedula, email_personal, nombre, apellido, estado "
        "FROM cinco_base_de_personal"
    )
    with connections["azul"].cursor() as cursor:
        cursor.execute(query)
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            for row in rows:
                yield row


def main() -> int:
    """Ejecuta el flujo principal de sincronización de usuarios hacia auth_user."""
    parser = build_parser()
    args = parser.parse_args()

    setup_django()

    from django.contrib.auth.models import User
    from django.db import IntegrityError, connections, router, transaction

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_count = get_total_rows()
    print(f"Total de registros a procesar: {total_count}")

    existing_ids = set(User.objects.values_list("id", flat=True))
    existing_usernames = set(User.objects.values_list("username", flat=True))

    created_count = 0
    updated_count = 0
    skipped_count = 0
    processed_count = 0

    csv_file = None
    csv_writer = None
    if args.output:
        csv_file = output_path.open("w", newline="", encoding="utf-8")
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(["username", "temp_password", "email"])  # nosec B608

    try:
        for source_id, cedula, email, nombre, apellido, estado in fetch_source_rows(args.batch_size):
            processed_count += 1
            if processed_count % 10 == 0 or processed_count == total_count:
                percent = (processed_count / total_count) * 100 if total_count > 0 else 0
                print(
                    f"\rProgreso: {processed_count}/{total_count} ({percent:.1f}%) | "
                    f"Creados: {created_count} | Saltados: {skipped_count}",
                    end="",
                    flush=True,
                )

            username = normalize_text(cedula)
            if not username:
                skipped_count += 1
                continue

            first_name = normalize_text(nombre)
            last_name = normalize_text(apellido)
            email_value = normalize_text(email)
            is_active = is_active_from_estado(estado)

            already_synced = (source_id in existing_ids) or (username in existing_usernames)

            if args.dry_run:
                if already_synced:
                    skipped_count += 1
                else:
                    created_count += 1
                    existing_ids.add(source_id)
                    existing_usernames.add(username)
                    if csv_writer:
                        csv_writer.writerow([username, "DRY_RUN", email_value])
                continue

            if already_synced:
                skipped_count += 1
                continue

            user = User(
                id=source_id,
                username=username,
                email=email_value,
                first_name=first_name,
                last_name=last_name,
                is_active=is_active,
                is_staff=False,
                is_superuser=False,
            )
            temp_password = username
            user.set_password(temp_password)
            database = router.db_for_write(User, instance=user)
            try:
                with transaction.atomic(using=database):
                    user.save(force_insert=True, using=database)
            except IntegrityError as error:
                if not is_identity_conflict(error, connections[database].vendor):
                    raise
                skipped_count += 1
                continue
            existing_ids.add(source_id)
            existing_usernames.add(username)
            created_count += 1
            if csv_writer:
                csv_writer.writerow([username, temp_password, email_value])
    finally:
        if csv_file:
            csv_file.close()

    print()  # Salto de línea para limpiar la barra de progreso
    print(
        "Import finalizado. "
        f"Creados: {created_count}. "
        f"Actualizados: {updated_count}. "
        f"Saltados: {skipped_count}."
    )
    if args.output:
        print(f"CSV generado: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
