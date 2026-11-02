"""TokenBlocklist con reloj simulado."""

from api.auth import TokenBlocklist


def test_revoked_token_is_detected_and_others_are_not():
    blocklist = TokenBlocklist(clock=lambda: 100)
    blocklist.revoke('a', expires_at=200)
    assert blocklist.is_revoked('a') and not blocklist.is_revoked('b')


def test_expired_entries_are_pruned_on_the_next_revocation():
    now = [100]
    blocklist = TokenBlocklist(clock=lambda: now[0])
    blocklist.revoke('old', expires_at=150)
    now[0] = 151
    blocklist.revoke('new', expires_at=300)
    assert not blocklist.is_revoked('old') and blocklist.is_revoked('new')
