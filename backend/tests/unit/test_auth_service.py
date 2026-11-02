"""AuthService con repositorio y hasher simulados: contrasenas y enumeracion de cuentas."""

from unittest.mock import create_autospec

import pytest

from application.identity.services import AuthService
from domain.identity.ports import PasswordHasher, UserRepository
from domain.shared.errors import AuthenticationFailed, InvalidInput
from domain.shared.ports import UnitOfWork
from tests.unit.factories import make_mechanic

DATA = {'first_name': 'Ana', 'last_name': 'Ruiz', 'document_number': '2001', 'email': 'ana@test.com'}


@pytest.fixture
def deps():
    users = create_autospec(UserRepository, instance=True)
    users.get_by_email.return_value = None
    users.get_by_document.return_value = None
    users.add.side_effect = lambda user: user
    hasher = create_autospec(PasswordHasher, instance=True)
    hasher.hash.return_value = 'dummy-hash'
    return {'users': users, 'hasher': hasher, 'uow': create_autospec(UnitOfWork, instance=True)}


def test_unknown_email_still_verifies_a_hash_to_hide_which_accounts_exist(deps):
    deps['hasher'].verify.return_value = True  # ni acertando la contrasena del hash ficticio entra

    with pytest.raises(AuthenticationFailed) as error:
        AuthService(**deps).authenticate('nadie@test.com', 'clave')

    assert error.value.message == 'Credenciales inválidas'
    deps['hasher'].verify.assert_called_once_with('dummy-hash', 'clave')


def test_the_dummy_hash_is_computed_only_once(deps):
    service = AuthService(**deps)
    for _ in range(2):
        with pytest.raises(AuthenticationFailed):
            service.authenticate('nadie@test.com', 'clave')
    deps['hasher'].hash.assert_called_once()


def test_wrong_password_uses_the_same_message_as_unknown_email(deps):
    deps['users'].get_by_email.return_value = make_mechanic()
    deps['hasher'].verify.return_value = False
    with pytest.raises(AuthenticationFailed) as error:
        AuthService(**deps).authenticate('mechanic@test.com', 'mala')
    assert error.value.message == 'Credenciales inválidas'


@pytest.mark.parametrize('password, accepted', [('1234567', False), ('12345678', True)])
def test_password_minimum_length(deps, password, accepted):
    service = AuthService(**deps)
    if accepted:
        assert service.register({**DATA, 'password': password}).role == 'client'
    else:
        with pytest.raises(InvalidInput) as error:
            service.register({**DATA, 'password': password})
        assert error.value.message == 'La contraseña debe tener al menos 8 caracteres'
        deps['users'].add.assert_not_called()
