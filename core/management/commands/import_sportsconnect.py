"""
Management command to import a SportsConnect CSV file.

Usage:
    python manage.py import_sportsconnect path/to/file.csv
    python manage.py import_sportsconnect path/to/file.csv --season "Spring 2026"
    python manage.py import_sportsconnect path/to/file.csv --dry-run
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.importers import SportsConnectImporter
from players.models import League, Season


class Command(BaseCommand):
    help = 'Import a SportsConnect CSV file into the League Management System.'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the SportsConnect CSV file.')
        parser.add_argument(
            '--season',
            type=str,
            default=None,
            help='Season name to import into (e.g., "Spring 2026"). Defaults to active season.',
        )
        parser.add_argument(
            '--league',
            type=str,
            default='SFLL',
            help='League short name. Defaults to SFLL.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Parse and validate the CSV without writing to the database.',
        )

    def handle(self, *args, **options):
        csv_path = options['csv_file']
        league_name = options['league']
        season_name = options['season']
        dry_run = options['dry_run']

        # Resolve league
        try:
            league = League.objects.get(short_name=league_name)
        except League.DoesNotExist:
            raise CommandError(f'League "{league_name}" not found.')

        # Resolve season
        if season_name:
            try:
                season = Season.objects.get(league=league, name=season_name)
            except Season.DoesNotExist:
                raise CommandError(f'Season "{season_name}" not found for league {league_name}.')
        else:
            season = Season.objects.filter(league=league, is_active=True).first()
            if not season:
                raise CommandError('No active season found. Use --season to specify one.')

        self.stdout.write(f'League:  {league.name}')
        self.stdout.write(f'Season:  {season.name}')
        self.stdout.write(f'CSV:     {csv_path}')
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no changes will be saved'))
        self.stdout.write('')

        # Read CSV
        try:
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                csv_content = f.read()
        except FileNotFoundError:
            raise CommandError(f'File not found: {csv_path}')
        except Exception as exc:
            raise CommandError(f'Error reading file: {exc}')

        # Run import
        importer = SportsConnectImporter(league=league, season=season)

        if dry_run:
            sid = transaction.savepoint()
            try:
                import_run = importer.run(csv_content)
                self._print_summary(import_run, importer)
            finally:
                transaction.savepoint_rollback(sid)
                self.stdout.write(self.style.WARNING('\nDry run complete — all changes rolled back.'))
        else:
            import_run = importer.run(csv_content)
            self._print_summary(import_run, importer)

    def _print_summary(self, import_run, importer):
        """Print a human-readable summary of the import."""
        stats = importer.stats
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('=== Import Summary ==='))
        self.stdout.write(f'  Status:              {import_run.status}')
        self.stdout.write(f'  Total rows:          {stats["total_rows"]}')
        self.stdout.write(f'  New players:         {stats["new_players"]}')
        self.stdout.write(f'  New registrations:   {stats["new_player_seasons"]}')
        self.stdout.write(f'  Updated records:     {stats["updated_records"]}')
        self.stdout.write(f'  Flagged for review:  {stats["flagged_for_review"]}')
        self.stdout.write(f'  Errors:              {stats["errors"]}')

        if import_run.error_details:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR('Errors:'))
            for err in import_run.error_details:
                self.stdout.write(f'  - {err}')

        if stats['flagged_for_review'] > 0:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                f'{stats["flagged_for_review"]} record(s) flagged for review.'
            ))
            if import_run.pk:
                self.stdout.write(f'  Review at: /admin/imports/{import_run.pk}/review/')

        if import_run.status == 'completed':
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('Import completed successfully.'))
        elif import_run.status == 'failed':
            self.stdout.write('')
            self.stdout.write(self.style.ERROR('Import failed.'))
