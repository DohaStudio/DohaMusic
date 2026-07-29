from sqlalchemy import inspect


def test_database_storage_and_health_are_initialized(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    inspector = inspect(client.app.state.session_factory.kw["bind"])
    assert {
        "generation_jobs",
        "generated_files",
        "stem_jobs",
        "stem_files",
        "pipeline_jobs",
        "pipeline_files",
        "voice_profiles",
        "alembic_version",
    }.issubset(set(inspector.get_table_names()))

    storage = client.app.state.storage
    assert storage.inputs_dir.is_dir()
    assert storage.outputs_dir.is_dir()
    assert storage.voices_dir.is_dir()
    assert storage.sample_file.is_file()
    assert storage.stem_vocals_dir.is_dir()
    assert storage.stem_instrumentals_dir.is_dir()
    assert storage.stem_metadata_dir.is_dir()
    assert storage.pipeline_dir.is_dir()
