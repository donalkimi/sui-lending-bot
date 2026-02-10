"""
Allocator Settings Service

Manages CRUD operations for allocator settings persistence.
Supports both PostgreSQL (Supabase) and SQLite backends.

Key Features:
- Save/load allocation constraints and sidebar filters
- Special 'last_used' record for auto-save
- Named presets with UUIDs
- UPSERT logic for both database types
- Graceful error handling with fallback to defaults

Usage:
    from analysis.allocator_settings_service import AllocatorSettingsService

    conn = get_db_connection()
    service = AllocatorSettingsService(conn)

    # Save settings
    service.save_settings(
        settings_id='last_used',
        settings_name='Last Used Settings',
        allocator_constraints={...},
        sidebar_filters={...}
    )

    # Load settings
    settings = service.load_settings('last_used')

    conn.close()
"""

import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
import pandas as pd


class AllocatorSettingsService:
    """Service for managing allocator settings persistence."""

    def __init__(self, conn):
        """
        Initialize service with database connection.

        Args:
            conn: Database connection (psycopg2 or sqlite3)
        """
        self.conn = conn
        self.cursor = conn.cursor()

        # Detect database type
        self.db_type = self._detect_database_type()

    def _detect_database_type(self) -> str:
        """
        Detect whether we're using PostgreSQL or SQLite.

        Returns:
            'postgresql' or 'sqlite'
        """
        try:
            # Try PostgreSQL-specific attribute
            if hasattr(self.conn, 'get_dsn_parameters'):
                return 'postgresql'
            # Try SQLite-specific attribute
            elif hasattr(self.conn, 'total_changes'):
                return 'sqlite'
            else:
                # Fallback: assume PostgreSQL (Supabase is more common in production)
                return 'postgresql'
        except Exception:
            return 'postgresql'

    def _get_placeholder(self) -> str:
        """
        Get SQL parameter placeholder for current database.

        Returns:
            '%s' for PostgreSQL, '?' for SQLite
        """
        return '%s' if self.db_type == 'postgresql' else '?'

    def save_settings(
        self,
        settings_id: str,
        settings_name: str,
        allocator_constraints: Dict[str, Any],
        sidebar_filters: Dict[str, Any],
        user_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> str:
        """
        Save allocator settings (UPSERT).

        For new records: creates with use_count=1
        For existing records: increments use_count, updates timestamps

        Args:
            settings_id: Primary key ('last_used' or UUID)
            settings_name: Display name
            allocator_constraints: Dict with allocation settings
            sidebar_filters: Dict with sidebar filter settings
            user_id: Optional user ID for multi-user support
            description: Optional description

        Returns:
            settings_id

        Raises:
            Exception: If database operation fails
        """
        try:
            # Build settings JSON
            settings_json = json.dumps({
                'allocator_constraints': allocator_constraints,
                'sidebar_filters': sidebar_filters
            })

            placeholder = self._get_placeholder()

            if self.db_type == 'postgresql':
                # PostgreSQL UPSERT with ON CONFLICT
                query = f"""
                    INSERT INTO allocator_settings (
                        settings_id, settings_name, settings_json,
                        user_id, description, last_used_at, use_count,
                        created_at, updated_at
                    ) VALUES (
                        {placeholder}, {placeholder}, {placeholder},
                        {placeholder}, {placeholder}, CURRENT_TIMESTAMP, 1,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    ON CONFLICT (settings_id) DO UPDATE SET
                        settings_name = EXCLUDED.settings_name,
                        settings_json = EXCLUDED.settings_json,
                        user_id = EXCLUDED.user_id,
                        description = EXCLUDED.description,
                        last_used_at = CURRENT_TIMESTAMP,
                        use_count = allocator_settings.use_count + 1,
                        updated_at = CURRENT_TIMESTAMP
                """
                params = (settings_id, settings_name, settings_json, user_id, description)

            else:  # SQLite
                # SQLite UPSERT using INSERT OR REPLACE with COALESCE for use_count
                query = f"""
                    INSERT OR REPLACE INTO allocator_settings (
                        settings_id, settings_name, settings_json,
                        user_id, description, last_used_at,
                        use_count, created_at, updated_at
                    ) VALUES (
                        {placeholder}, {placeholder}, {placeholder},
                        {placeholder}, {placeholder}, CURRENT_TIMESTAMP,
                        COALESCE(
                            (SELECT use_count + 1 FROM allocator_settings WHERE settings_id = {placeholder}),
                            1
                        ),
                        COALESCE(
                            (SELECT created_at FROM allocator_settings WHERE settings_id = {placeholder}),
                            CURRENT_TIMESTAMP
                        ),
                        CURRENT_TIMESTAMP
                    )
                """
                params = (settings_id, settings_name, settings_json, user_id, description,
                         settings_id, settings_id)

            self.cursor.execute(query, params)
            self.conn.commit()

            return settings_id

        except Exception as e:
            self.conn.rollback()
            print(f"Error saving settings: {e}")
            raise

    def load_settings(self, settings_id: str) -> Optional[Dict[str, Any]]:
        """
        Load settings by ID.

        Args:
            settings_id: Primary key to load

        Returns:
            Dict with 'allocator_constraints', 'sidebar_filters', and 'metadata'
            None if not found or on error
        """
        try:
            placeholder = self._get_placeholder()

            query = f"""
                SELECT settings_json, settings_name, description,
                       last_used_at, use_count, created_at, updated_at
                FROM allocator_settings
                WHERE settings_id = {placeholder}
            """

            self.cursor.execute(query, (settings_id,))
            row = self.cursor.fetchone()

            if not row:
                return None

            # Parse JSON
            settings_json_str = row[0]
            settings_data = json.loads(settings_json_str)

            # Merge with defaults to handle missing keys
            merged_settings = self._merge_with_defaults(settings_data)

            return {
                'allocator_constraints': merged_settings['allocator_constraints'],
                'sidebar_filters': merged_settings['sidebar_filters'],
                'metadata': {
                    'settings_name': row[1],
                    'description': row[2],
                    'last_used_at': row[3],
                    'use_count': row[4],
                    'created_at': row[5],
                    'updated_at': row[6]
                }
            }

        except json.JSONDecodeError as e:
            print(f"Error parsing JSON for settings_id={settings_id}: {e}")
            return None
        except Exception as e:
            print(f"Error loading settings: {e}")
            return None

    def load_last_used(self, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Load 'last_used' settings (convenience method).

        Args:
            user_id: Optional user ID for multi-user support

        Returns:
            Settings dict or None
        """
        return self.load_settings('last_used')

    def get_all_presets(self, user_id: Optional[str] = None) -> pd.DataFrame:
        """
        Get all named presets (excludes 'last_used').

        Args:
            user_id: Optional user ID for filtering

        Returns:
            DataFrame with columns: settings_id, settings_name, last_used_at,
            use_count, description
        """
        try:
            placeholder = self._get_placeholder()

            query = f"""
                SELECT settings_id, settings_name, last_used_at,
                       use_count, description
                FROM allocator_settings
                WHERE settings_id != {placeholder}
                ORDER BY last_used_at DESC
            """

            self.cursor.execute(query, ('last_used',))
            rows = self.cursor.fetchall()

            if not rows:
                return pd.DataFrame(columns=['settings_id', 'settings_name', 'last_used_at',
                                            'use_count', 'description'])

            df = pd.DataFrame(rows, columns=['settings_id', 'settings_name', 'last_used_at',
                                            'use_count', 'description'])
            return df

        except Exception as e:
            print(f"Error getting presets: {e}")
            return pd.DataFrame(columns=['settings_id', 'settings_name', 'last_used_at',
                                        'use_count', 'description'])

    def create_named_preset(
        self,
        preset_name: str,
        allocator_constraints: Dict[str, Any],
        sidebar_filters: Dict[str, Any],
        description: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> str:
        """
        Create a new named preset with generated UUID.

        Args:
            preset_name: Display name for preset
            allocator_constraints: Dict with allocation settings
            sidebar_filters: Dict with sidebar filter settings
            description: Optional description
            user_id: Optional user ID

        Returns:
            Generated preset_id (UUID)
        """
        preset_id = uuid.uuid4().hex

        self.save_settings(
            settings_id=preset_id,
            settings_name=preset_name,
            allocator_constraints=allocator_constraints,
            sidebar_filters=sidebar_filters,
            user_id=user_id,
            description=description
        )

        return preset_id

    def update_preset(
        self,
        settings_id: str,
        settings_name: Optional[str] = None,
        allocator_constraints: Optional[Dict[str, Any]] = None,
        sidebar_filters: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None
    ) -> bool:
        """
        Update an existing preset (partial update).

        Args:
            settings_id: ID of preset to update
            settings_name: New name (optional)
            allocator_constraints: New constraints (optional)
            sidebar_filters: New filters (optional)
            description: New description (optional)

        Returns:
            True if updated, False if not found

        Raises:
            ValueError: If settings_id not found
        """
        # Load existing settings
        existing = self.load_settings(settings_id)

        if not existing:
            raise ValueError(f"Settings not found: {settings_id}")

        # Merge with new values
        final_name = settings_name if settings_name is not None else existing['metadata']['settings_name']
        final_constraints = allocator_constraints if allocator_constraints is not None else existing['allocator_constraints']
        final_filters = sidebar_filters if sidebar_filters is not None else existing['sidebar_filters']
        final_description = description if description is not None else existing['metadata']['description']

        # Save (will update via UPSERT)
        self.save_settings(
            settings_id=settings_id,
            settings_name=final_name,
            allocator_constraints=final_constraints,
            sidebar_filters=final_filters,
            description=final_description
        )

        return True

    def delete_preset(self, settings_id: str) -> bool:
        """
        Delete a preset.

        Args:
            settings_id: ID of preset to delete

        Returns:
            True if deleted, False if not found

        Raises:
            ValueError: If attempting to delete 'last_used'
        """
        if settings_id == 'last_used':
            raise ValueError("Cannot delete 'last_used' settings")

        try:
            placeholder = self._get_placeholder()

            query = f"""
                DELETE FROM allocator_settings
                WHERE settings_id = {placeholder}
            """

            self.cursor.execute(query, (settings_id,))
            self.conn.commit()

            # Check if any rows were deleted
            deleted_count = self.cursor.rowcount
            return deleted_count > 0

        except Exception as e:
            self.conn.rollback()
            print(f"Error deleting preset: {e}")
            return False

    def _merge_with_defaults(self, loaded_settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge loaded settings with defaults to handle missing keys.

        Args:
            loaded_settings: Loaded settings dict (may have missing keys)

        Returns:
            Complete settings dict with defaults filled in
        """
        from config.settings import DEFAULT_ALLOCATION_CONSTRAINTS, DEFAULT_DEPLOYMENT_USD

        # Default allocator constraints
        default_allocator = DEFAULT_ALLOCATION_CONSTRAINTS.copy()
        default_allocator['portfolio_size'] = DEFAULT_DEPLOYMENT_USD

        # Default sidebar filters
        default_sidebar = {
            'liquidation_distance': 0.20,
            'deployment_usd': DEFAULT_DEPLOYMENT_USD,
            'force_usdc_start': False,
            'force_token3_equals_token1': False,
            'stablecoin_only': False,
            'min_net_apr': 0.0,
            'token_filter': [],
            'protocol_filter': []
        }

        # Merge allocator constraints
        allocator_constraints = default_allocator.copy()
        allocator_constraints.update(loaded_settings.get('allocator_constraints', {}))

        # Merge sidebar filters
        sidebar_filters = default_sidebar.copy()
        sidebar_filters.update(loaded_settings.get('sidebar_filters', {}))

        return {
            'allocator_constraints': allocator_constraints,
            'sidebar_filters': sidebar_filters
        }
