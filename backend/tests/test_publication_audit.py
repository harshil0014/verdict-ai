import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location('publication_audit',Path(__file__).resolve().parents[2]/'scripts/audit_publication.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


def test_public_author_username_exception_is_limited_to_commit_identity_headers():
    user=b'public-author';email=user+b'@example.test'
    header=b'author Public Author <'+email+b'> 1 +0000\n'
    cleaned=audit.without_public_username_metadata(header,user,email,'commit',{user})
    assert user not in cleaned
    assert user in audit.without_public_username_metadata(header,user,email,'blob',{user})
    assert user in audit.without_public_username_metadata(header+b'\nPrivate data: '+user,user,email,'commit',{user})
    assert user in audit.without_public_username_metadata(header,user,email,'commit',set())
    assert b'password-secret' in audit.without_public_username_metadata(header+b'\npassword-secret',b'password-secret',email,'commit',{user})
