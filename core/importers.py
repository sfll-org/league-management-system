"""
SportsConnect CSV importer for the SFLL — League Management System.

Parses SportsConnect registration CSVs and syncs players, divisions,
and season registrations into the database with delta detection and
anomaly flagging.
"""

import csv
import io
import logging
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from core.models import ImportFlag, ImportRun
from players.models import Division, Player, PlayerSeason

logger = logging.getLogger(__name__)

# Map normalized column names to the internal field names we use.
# SportsConnect CSVs have inconsistent casing and spacing; we normalize
# by lowercasing and stripping whitespace before lookup.
COLUMN_MAP = {
    'order_id': 'order_id',
    'order detail id': 'order_detail_id',
    'player first name': 'player_first_name',
    'player last name': 'player_last_name',
    'player id': 'sportsconnect_player_id',
    'player age': 'player_age',
    'division name': 'division_name',
    'account first name': 'account_first_name',
    'account last name': 'account_last_name',
    'user email': 'user_email',
    'additional email': 'additional_email',
    'program name': 'program_name',
    'team name': 'team_name',
    'session_id': 'session_id',
    'status': 'status',
    'player date of birth': 'player_dob',
    'player dob': 'player_dob',
    'date of birth': 'player_dob',
}


def _normalize_key(key):
    """Lowercase, strip whitespace, collapse internal whitespace."""
    return ' '.join(key.lower().strip().split())


def _parse_date(value):
    """Try common date formats from SportsConnect exports."""
    if not value or not value.strip():
        return None
    value = value.strip()
    for fmt in ('%m/%d/%Y', '%Y-%m-%d', '%m-%d-%Y', '%m/%d/%y'):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


class SportsConnectImporter:
    """Parse a SportsConnect CSV and sync with the database."""

    def __init__(self, league, season, user=None):
        self.league = league
        self.season = season
        self.user = user
        self.import_run = None
        self.stats = {
            'total_rows': 0,
            'new_players': 0,
            'new_player_seasons': 0,
            'updated_records': 0,
            'flagged_for_review': 0,
            'errors': 0,
        }
        self._division_cache = {}
        self._error_details = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, csv_file):
        """Process a CSV file object. Returns the ImportRun record."""
        self.import_run = ImportRun.objects.create(
            league=self.league,
            status='running',
            triggered_by='manual' if self.user else 'scheduled',
        )

        try:
            self._load_division_cache()
            self._process_csv(csv_file)
            self.import_run.status = 'completed'
        except Exception as exc:
            logger.exception('Import failed: %s', exc)
            self.import_run.status = 'failed'
            self._error_details.append(f'Fatal error: {exc}')

        self.import_run.completed_at = timezone.now()
        self.import_run.total_rows = self.stats['total_rows']
        self.import_run.new_players = self.stats['new_players']
        self.import_run.new_player_seasons = self.stats['new_player_seasons']
        self.import_run.updated_records = self.stats['updated_records']
        self.import_run.flagged_for_review = self.stats['flagged_for_review']
        self.import_run.errors = self.stats['errors']
        self.import_run.error_details = self._error_details
        self.import_run.save()

        return self.import_run

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load_division_cache(self):
        """Pre-load divisions for fast name lookup."""
        for div in Division.objects.filter(league=self.league):
            self._division_cache[div.name.lower().strip()] = div

    def _process_csv(self, csv_file):
        """Read CSV content and process each row."""
        # Accept file-like objects or raw bytes/strings
        if hasattr(csv_file, 'read'):
            raw = csv_file.read()
        else:
            raw = csv_file

        if isinstance(raw, bytes):
            raw = raw.decode('utf-8-sig')  # handle BOM

        reader = csv.DictReader(io.StringIO(raw))

        # Build column mapping from the header
        col_map = {}
        if reader.fieldnames:
            for col in reader.fieldnames:
                normalized = _normalize_key(col)
                if normalized in COLUMN_MAP:
                    col_map[col] = COLUMN_MAP[normalized]

        for row_num, row in enumerate(reader, start=2):  # row 1 = header
            # Skip completely blank rows
            if not any(v.strip() for v in row.values() if v):
                continue

            self.stats['total_rows'] += 1

            try:
                mapped = {col_map.get(k, k): (v.strip() if v else '') for k, v in row.items()}
                self._process_row(mapped, row_num)
            except Exception as exc:
                logger.warning('Row %d error: %s', row_num, exc)
                self.stats['errors'] += 1
                self._error_details.append(f'Row {row_num}: {exc}')

    @transaction.atomic
    def _process_row(self, row, row_num):
        """Process a single mapped CSV row."""
        sc_player_id = row.get('sportsconnect_player_id', '')
        if not sc_player_id:
            self.stats['errors'] += 1
            self._error_details.append(f'Row {row_num}: Missing Player Id')
            return

        first_name = row.get('player_first_name', '')
        last_name = row.get('player_last_name', '')
        if not first_name or not last_name:
            self.stats['errors'] += 1
            self._error_details.append(f'Row {row_num}: Missing player name')
            return

        # ----- Division -----
        division_name = row.get('division_name', '')
        division = self._resolve_division(division_name, row_num)

        # ----- Player (find or create) -----
        player, player_created = Player.objects.get_or_create(
            sportsconnect_player_id=sc_player_id,
            defaults={
                'league': self.league,
                'first_name': first_name,
                'last_name': last_name,
                'date_of_birth': _parse_date(row.get('player_dob', '')),
            },
        )

        if player_created:
            self.stats['new_players'] += 1
        else:
            # Detect name changes
            updated = False
            if player.first_name != first_name or player.last_name != last_name:
                self._create_flag(
                    'data_mismatch',
                    details={
                        'row': row_num,
                        'field': 'player_name',
                        'existing': f'{player.first_name} {player.last_name}',
                        'incoming': f'{first_name} {last_name}',
                        'sportsconnect_player_id': sc_player_id,
                    },
                )
                # Update to the latest name from SportsConnect
                player.first_name = first_name
                player.last_name = last_name
                updated = True

            dob = _parse_date(row.get('player_dob', ''))
            if dob and player.date_of_birth and dob != player.date_of_birth:
                self._create_flag(
                    'data_mismatch',
                    details={
                        'row': row_num,
                        'field': 'date_of_birth',
                        'existing': str(player.date_of_birth),
                        'incoming': str(dob),
                        'sportsconnect_player_id': sc_player_id,
                    },
                )
            elif dob and not player.date_of_birth:
                player.date_of_birth = dob
                updated = True

            if updated:
                player.save()
                self.stats['updated_records'] += 1

        # ----- Duplicate detection -----
        self._check_duplicates(player, first_name, last_name)

        # ----- PlayerSeason (find or create) -----
        order_detail_id = row.get('order_detail_id', '')
        order_id = row.get('order_id', '')
        account_name = f"{row.get('account_first_name', '')} {row.get('account_last_name', '')}".strip()
        account_email = row.get('user_email', '')
        additional_email = row.get('additional_email', '')

        ps, ps_created = PlayerSeason.objects.get_or_create(
            player=player,
            season=self.season,
            defaults={
                'division': division,
                'status': 'registered',
                'order_id': order_id,
                'sportsconnect_order_detail_id': order_detail_id,
                'account_name': account_name,
                'account_email': account_email,
                'additional_email': additional_email,
            },
        )

        if ps_created:
            self.stats['new_player_seasons'] += 1
        else:
            # Update contact info and detect division changes
            changes = {}

            if division and ps.division and division != ps.division:
                self._create_flag(
                    'division_change',
                    player_season=ps,
                    details={
                        'row': row_num,
                        'player': player.full_name,
                        'sportsconnect_player_id': sc_player_id,
                        'previous_division': ps.division.name,
                        'new_division': division.name,
                    },
                )
                ps.division = division
                changes['division'] = True

            if account_email and account_email != ps.account_email:
                if ps.account_email:
                    self._create_flag(
                        'data_mismatch',
                        player_season=ps,
                        details={
                            'row': row_num,
                            'field': 'account_email',
                            'existing': ps.account_email,
                            'incoming': account_email,
                            'player': player.full_name,
                        },
                    )
                ps.account_email = account_email
                changes['account_email'] = True

            if account_name and account_name != ps.account_name:
                ps.account_name = account_name
                changes['account_name'] = True

            if additional_email and additional_email != ps.additional_email:
                ps.additional_email = additional_email
                changes['additional_email'] = True

            if order_detail_id and order_detail_id != ps.sportsconnect_order_detail_id:
                ps.sportsconnect_order_detail_id = order_detail_id
                changes['order_detail_id'] = True

            if changes:
                ps.save()
                self.stats['updated_records'] += 1

        # ----- Cancellation detection -----
        self._check_cancellation(row, ps, row_num)

    def _resolve_division(self, division_name, row_num):
        """Look up a Division by name. Flag if not found."""
        if not division_name:
            return None

        key = division_name.lower().strip()
        division = self._division_cache.get(key)

        if division is None:
            self._create_flag(
                'data_mismatch',
                details={
                    'row': row_num,
                    'field': 'division_name',
                    'message': f'Unknown division: "{division_name}"',
                },
            )
        return division

    def _check_duplicates(self, player, first_name, last_name):
        """Flag potential duplicates: same name + DOB, different SC ID."""
        dupes = Player.objects.filter(
            league=self.league,
            first_name__iexact=first_name,
            last_name__iexact=last_name,
        ).exclude(pk=player.pk)

        if player.date_of_birth:
            dupes = dupes.filter(date_of_birth=player.date_of_birth)

        for dupe in dupes:
            self._create_flag(
                'potential_duplicate',
                details={
                    'player_name': f'{first_name} {last_name}',
                    'existing_sc_id': dupe.sportsconnect_player_id,
                    'incoming_sc_id': player.sportsconnect_player_id,
                    'existing_player_id': dupe.pk,
                    'incoming_player_id': player.pk,
                },
            )

    def _check_cancellation(self, row, player_season, row_num):
        """Detect rows that indicate a cancellation or withdrawal."""
        status = row.get('status', '').lower()
        program = row.get('program_name', '').lower()

        cancel_keywords = ['cancel', 'refund', 'withdraw', 'dropped', 'void']
        is_cancelled = any(kw in status for kw in cancel_keywords) or \
                       any(kw in program for kw in cancel_keywords)

        if is_cancelled:
            self._create_flag(
                'cancellation',
                player_season=player_season,
                details={
                    'row': row_num,
                    'player': player_season.player.full_name,
                    'status': row.get('status', ''),
                    'program': row.get('program_name', ''),
                },
            )

    def _create_flag(self, flag_type, player_season=None, details=None):
        """Create an ImportFlag and increment the counter."""
        ImportFlag.objects.create(
            import_run=self.import_run,
            flag_type=flag_type,
            player_season=player_season,
            details=details or {},
        )
        self.stats['flagged_for_review'] += 1
