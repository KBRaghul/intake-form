from app.core.security import hash_password, verify_password


def test_hash_is_not_plain_password():
    assert hash_password("s3cret-pass") != "s3cret-pass"


def test_verify_correct_password():
    hashed = hash_password("s3cret-pass")
    assert verify_password("s3cret-pass", hashed)


def test_verify_wrong_password():
    hashed = hash_password("s3cret-pass")
    assert not verify_password("wrong-pass", hashed)


def test_same_password_gets_different_hashes():
    assert hash_password("s3cret-pass") != hash_password("s3cret-pass")
