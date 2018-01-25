# --
# Copyright (c) 2008-2018 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --

"""Securiy API for the applications"""

from nagare import local, partial


# ---------------------------------------------------------------------------

# API to access the security context

def _get_user():
    """Return the current user

    Return:
      - the user object (created by the security manager)
    """
    return local.request.user


def get_user():
    """Return the current user

    Return:
      - the user object (created by the security manager) if not expired
    """
    user = _get_user()
    return user if user is not None and not user.expired else None


def set_user(user):
    """Change the user

    In:
      - ``user`` -- the current user
    """
    local.request.user = user


def get_manager():
    """Return the security manager

    Each application has a dedicated security manager

    Return:
      - the security manager
    """
    return local.request.security_manager


def set_manager(manager):
    """Change the security manager

    In:
      - ``manager`` -- the new security manager
    """
    local.request.security_manager = manager


# ---------------------------------------------------------------------------

# def flatten(*args):
#     return sum([flatten(*x) if hasattr(x, '__iter__') else (x,) for x in args], ())


def has_permissions(perm, subject=None):
    """Check that the current user has the permissions ``perm``
    on the object ``subject``

    Forward the call to the generic method ``has_permission()`` of the
    current security manager

    .. note::

      The default generic method can check a single permission or a list of
      permissions

    In:
      - ``perm`` -- permission(s)
      - ``subject`` -- object to check the permissions on

    Return:
      - True if the access is granted
      - Else a ``security.common.denial`` object
    """
    return get_manager().has_permission(get_user(), perm, subject)


def check_permissions(perm, subject=None):
    """Control that the current user has the permissions ``perm``
    on the object ``subject``

    Forward the call to the generic method ``has_permission()`` of the
    current security manager.

    Then let the security manager acts if the permission is denied.

    .. note::

      The default generic method can check a single permission or a list of
      permissions

    In:
      - ``perm`` -- permission(s)
      - ``subject`` -- object to check the permissions on

    Return:
      - True if the access is granted
      - Else a ``security.common.denial`` object
    """
    credential = has_permissions(perm, subject)
    if not credential:
        if credential is False:
            credential = ''
        get_manager().denies(credential)

    return credential


def call_with_permissions(self, __action, __perm, __subject, *args, **kw):
    """Call a function or method only if permit

    In:
      - ``self`` -- if ``None`` then ``__action`` is a function else a method
      - ``__action`` -- function or method to call
      - ``__perm`` -- permission(s) to check
      - ``__subject`` -- object to check the permissions on
      - ``args``, ``kw`` -- ``__action`` parameters

    Return:
      - ``__action`` return
    """
    check_permissions(__perm, __subject or self)
    return __action(self, *args, **kw) if self else __action(*args, **kw)


def wrapper(action, perm, subject):
    """Wrap a function or method into a wrapper that will check the user permissions

    In:
      - ``action`` -- function or method to wrapper
      - ``perm`` -- permission(s) to check
      - ``subject`` -- object to check the permissions on

    Return:
      - new action
    """
    if perm is not None:
        action = partial.Partial(call_with_permissions, None, action, perm, subject)

    return action


def permissions(perm, subject=None):
    """Decorator to check the permissions of the current user

    The ``subject`` will be the first argument of the decorated method

    In:
      - ``perm`` -- permission(s)
      - ``subject`` -- object to check the permissions on or the first argument
                       of the decorated method if ``None``
    """
    # perm = flatten(perm)
    return lambda f: partial.Decorator(f, call_with_permissions, perm, subject)


permissions_with_subject = permissions  # Obsolete
