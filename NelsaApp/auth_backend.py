"""
Custom auth: allow login with username (any casing), exact username, or email.

Django's ModelBackend only matches USERNAME_FIELD case-sensitively, which causes
valid passwords to fail when casing differs. Putting this backend first fixes that
without fighting AuthenticationForm.clean().
"""

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


class EmailOrUsernameInsensitiveBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if username is None or password is None:
            return None

        login = str(username).strip()
        if not login:
            return None

        user = None

        # 1) Exact natural key (default Django behaviour)
        try:
            user = UserModel._default_manager.get_by_natural_key(login)
        except UserModel.DoesNotExist:
            pass

        # 2) Case-insensitive username
        if user is None:
            user = UserModel.objects.filter(username__iexact=login).first()

        # 3) Email (users often type email in the "username" field)
        if user is None:
            user = UserModel.objects.filter(email__iexact=login).first()

        if user is None:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
