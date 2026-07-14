import pytest

from app.shared.auth import hash_key
from app.shared.database import SessionLocal
from app.shared.models import ApiKey
from scripts.manage_keys import issue, list_keys, revoke


@pytest.fixture(autouse=True)
def _cleanup_test_keys():
    yield
    with SessionLocal() as session:
        session.query(ApiKey).filter(ApiKey.label.like("test-manage-keys%")).delete()
        session.commit()


def test_issue_creates_row_with_matching_hash(capsys):
    issue("test-manage-keys-issue")
    output = capsys.readouterr().out
    plaintext = next(
        line for line in output.splitlines() if line.startswith("Key: ")
    ).removeprefix("Key: ")

    with SessionLocal() as session:
        api_key = session.query(ApiKey).filter(ApiKey.label == "test-manage-keys-issue").one()
        assert api_key.key_hash == hash_key(plaintext)
        assert api_key.revoked_at is None


def test_revoke_sets_revoked_at():
    issue("test-manage-keys-revoke")
    with SessionLocal() as session:
        key_id = (
            session.query(ApiKey).filter(ApiKey.label == "test-manage-keys-revoke").one().id
        )

    revoke(key_id)

    with SessionLocal() as session:
        api_key = session.get(ApiKey, key_id)
        assert api_key.revoked_at is not None


def test_revoke_nonexistent_id_exits_nonzero():
    with pytest.raises(SystemExit) as exc:
        revoke(999_999)
    assert exc.value.code == 1


def test_revoke_already_revoked_exits_nonzero():
    issue("test-manage-keys-double-revoke")
    with SessionLocal() as session:
        key_id = (
            session.query(ApiKey)
            .filter(ApiKey.label == "test-manage-keys-double-revoke")
            .one()
            .id
        )

    revoke(key_id)
    with pytest.raises(SystemExit) as exc:
        revoke(key_id)
    assert exc.value.code == 1


def test_list_keys_never_prints_key_hash(capsys):
    issue("test-manage-keys-list")
    capsys.readouterr()
    list_keys()
    output = capsys.readouterr().out
    assert "test-manage-keys-list" in output
    assert "key_hash" not in output
