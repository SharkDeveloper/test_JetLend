"""
Management command: import mailing records from an XLSX file.

Usage
─────
    python manage.py import_mailings path/to/file.xlsx
    python manage.py import_mailings path/to/file.xlsx --no-send
    python manage.py import_mailings path/to/file.xlsx --dry-run

Options
───────
--no-send   Import records into the database but do not dispatch Celery tasks.
--dry-run   Validate and count rows without writing anything to the database.
"""

import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from mailings.importer import ImportResult, import_mailings_from_xlsx, _iter_rows, _parse_row
from mailings.models import MailingRecord


class Command(BaseCommand):
    help = "Import mailing records from an XLSX file and dispatch email delivery tasks."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "xlsx_file",
            type=str,
            help="Path to the XLSX file to import.",
        )
        parser.add_argument(
            "--no-send",
            action="store_true",
            default=False,
            help="Import records into the DB but skip Celery task dispatch.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Validate and count rows without touching the database.",
        )

    def handle(self, *args, **options) -> None:
        path = Path(options["xlsx_file"])

        if not path.exists():
            raise CommandError(f"File not found: {path}")
        if path.suffix.lower() != ".xlsx":
            raise CommandError(f"Expected an .xlsx file, got: {path.suffix!r}")

        send   = not options["no_send"]
        dry_run = options["dry_run"]

        if dry_run:
            result = self._dry_run(path)
        else:
            self.stdout.write(f"Importing {path} …")
            try:
                result = import_mailings_from_xlsx(path, send=send)
            except ValueError as exc:
                raise CommandError(str(exc)) from exc

            if send:
                self.stdout.write("  Email tasks dispatched to Celery queue.")
            else:
                self.stdout.write("  --no-send: tasks were NOT dispatched.")

        self.stdout.write(str(result))

        # Exit with a non-zero code if there were any errors so CI pipelines
        # can detect partial failures.
        if result.errors:
            sys.exit(1)

    # ------------------------------------------------------------------
    def _dry_run(self, path: Path) -> ImportResult:
        """
        Validate rows and report what *would* happen without writing to the DB.
        """
        self.stdout.write(f"[DRY RUN] Validating {path} …")

        existing_ids: set[str] = set(
            MailingRecord.objects.values_list("external_id", flat=True)
        )
        seen: set[str] = set()

        result = ImportResult()

        try:
            row_iter = _iter_rows(path)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        for row_num, row_dict in row_iter:
            result.total_rows += 1
            try:
                row = _parse_row(row_dict, row_num)
            except ValueError as exc:
                result.errors += 1
                result.error_details.append(str(exc))
                continue

            if row.external_id in existing_ids or row.external_id in seen:
                result.skipped += 1
                continue

            seen.add(row.external_id)
            result.created += 1  # "would be created"

        self.stdout.write("  [DRY RUN] No changes were written to the database.")
        return result
