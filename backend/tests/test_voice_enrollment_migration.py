from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def _config(database_path: Path) -> Config:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")
    return config


def test_empty_database_upgrade_downgrade_and_reupgrade(tmp_path) -> None:
    database_path = tmp_path / "empty.db"
    config = _config(database_path)
    command.upgrade(config, "head")

    inspector = inspect(create_engine(f"sqlite:///{database_path.as_posix()}"))
    assert {"voice_enrollments", "voice_samples"}.issubset(inspector.get_table_names())
    assert "active_reference_sample_id" in {
        column["name"] for column in inspector.get_columns("voice_profiles")
    }
    assert {
        "ix_voice_enrollments_status_expires_at",
        "ix_voice_enrollments_cleanup_status",
    }.issubset({index["name"] for index in inspector.get_indexes("voice_enrollments")})
    assert {
        "ix_voice_samples_enrollment_id_status",
        "ix_voice_samples_voice_profile_id_status",
        "ix_voice_samples_status_expires_at",
    }.issubset({index["name"] for index in inspector.get_indexes("voice_samples")})
    command.downgrade(config, "20260731_0009")
    assert (
        "voice_samples"
        not in inspect(
            create_engine(f"sqlite:///{database_path.as_posix()}")
        ).get_table_names()
    )
    command.upgrade(config, "head")


def test_existing_profiles_are_backfilled_without_file_access(tmp_path) -> None:
    database_path = tmp_path / "legacy.db"
    config = _config(database_path)
    command.upgrade(config, "20260731_0009")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    now = datetime.now(UTC)
    missing_path = "voices/references/not-present.wav"
    with engine.begin() as connection:
        for profile_id in ("profile-one", "profile-two"):
            connection.execute(
                text(
                    "INSERT INTO voice_profiles ("
                    "id, name, reference_file_path, consent_confirmed, display_filename, "
                    "mime_type, size_bytes, duration_seconds, sample_rate, channels, status, "
                    "quality_warnings, consent_text_version, consent_confirmed_at, "
                    "created_at, updated_at) VALUES ("
                    ":id, :name, :path, 1, NULL, 'audio/wav', 1234, 5.5, 16000, 1, "
                    "'READY', '[]', 'v1', :now, :now, :now)"
                ),
                {
                    "id": profile_id,
                    "name": profile_id,
                    "path": missing_path,
                    "now": now,
                },
            )

    command.upgrade(config, "head")
    with engine.connect() as connection:
        rows = (
            connection.execute(
                text(
                    "SELECT p.id, p.active_reference_sample_id, s.source_type, s.status, "
                    "s.normalized_storage_path, s.original_storage_path, s.bit_depth, "
                    "s.quality_status FROM voice_profiles p JOIN voice_samples s "
                    "ON s.id = p.active_reference_sample_id ORDER BY p.id"
                )
            )
            .mappings()
            .all()
        )

    assert len(rows) == 2
    assert all(row["active_reference_sample_id"] for row in rows)
    assert all(row["source_type"] == "LEGACY_REFERENCE" for row in rows)
    assert all(row["status"] == "PROMOTED" for row in rows)
    assert all(row["normalized_storage_path"] == missing_path for row in rows)
    assert all(row["original_storage_path"] is None for row in rows)
    assert all(row["bit_depth"] is None for row in rows)
    assert all(row["quality_status"] is None for row in rows)
    assert not (tmp_path / missing_path).exists()

    command.downgrade(config, "20260731_0009")
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM voice_samples")) == 2
