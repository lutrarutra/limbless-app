from typing import Optional, Union

from ... import models
from .. import exceptions

def create_user(
        self, email: str, password: str,
        role: Union[models.UserRole, int], commit: bool = True
    ) -> models.User:
    persist_session = self._session is not None
    if not self._session:
        self.open_session()

    if not models.UserRole.is_valid(role):
        raise exceptions.InvalidRole(f"Invalid role {role}")
    
    if self._session.query(models.User).where(
        models.User.email == email
    ).first() is not None:
        raise exceptions.NotUniqueValue(f"User with email {email} already exists")
    
    user = models.User(
        email=email,
        password_hash=password, # FIXME: hash password
        role=role if isinstance(role, int) else role.value
    )

    self._session.add(user)
    if commit:
        self._session.commit()
        self._session.refresh(user)

    if not persist_session: self.close_session()
    return user

def get_user(self, user_id: int) -> models.User:
    persist_session = self._session is not None
    if not self._session:
        self.open_session()

    res = self._session.get(models.User, user_id)
    if not persist_session: self.close_session()
    return res

def get_users(self) -> list[models.User]:
    persist_session = self._session is not None
    if not self._session:
        self.open_session()

    users = self._session.query(models.User).all()
    if not persist_session: self.close_session()
    return users

def update_user(
        self, user_id: int,
        email: Optional[str] = None,
        password_hash: Optional[str] = None,
        role: Optional[Union[models.UserRole, int]] = None,
        commit: bool = True
    ) -> models.User:
    persist_session = self._session is not None
    if not self._session:
        self.open_session()

    user = self._session.get(models.User, user_id)
    if not user:
        raise exceptions.ElementDoesNotExist(f"User with id {user_id} does not exist")

    if email is not None: user.email = email
    if password_hash is not None: user.password_hash = password_hash
    if role is not None:
        if not models.UserRole.is_valid(role):
            raise exceptions.InvalidRole(f"Invalid role {role}")
        user.role = role

    if commit:
        self._session.commit()
        self._session.refresh(user)

    if not persist_session: self.close_session()
    return user

def delete_user(self, user_id: int, commit: bool = True) -> None:
    persist_session = self._session is not None
    if not self._session:
        self.open_session()
    
    user = self._session.get(models.User, user_id)
    if not user:
        raise exceptions.ElementDoesNotExist(f"User with id {user_id} does not exist")
    
    self._session.delete(user)
    
    if commit: self._session.commit()

    if not persist_session: self.close_session()