from sqlalchemy import inspect


def test_database_storage_and_health_are_initialized(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    inspector = inspect(client.app.state.session_factory.kw["bind"])
    assert {
        "generation_jobs",
        "generated_files",
        "voice_profiles",
        "alembic_version",
    }.issubset(set(inspector.get_table_names()))

    storage = client.app.state.storage
    assert storage.inputs_dir.is_dir()
    assert storage.outputs_dir.is_dir()
    assert storage.voices_dir.is_dir()
    assert storage.sample_file.is_file()
