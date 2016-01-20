from horus.events import PasswordResetEvent
from horus.views import get_config_route
from pyramid.httpexceptions import HTTPFound, HTTPNotFound
from pyramid.response import Response
from websauna.system.core import messages
from websauna.system.http import Request
from websauna.system.mail import send_templated_mail
from websauna.system.user.interfaces import ICredentialActivityService, CannotResetPasswordException, IUser
from websauna.system.user.utils import get_user_registry
from zope.interface import implementer

from websauna.compat.typing import Optional


@implementer(ICredentialActivityService)
class DefaultCredentialActivityService:
    """Handle password reset process and such."""

    def __init__(self, request: Request):
        self.request = request

    def activate(self, user_token: str, activation_code: str) -> Response:
        """Active a user after user activation email."""

        activation = self.Activation.get_by_code(self.request, code)

        if activation:
            user_uuid = slug_to_uuid(user_id)
            user = self.request.dbsession.query(User).filter_by(uuid=user_uuid).first()

            if not user or (user.activation != activation):
                return HTTPNotFound()

            if user:
                self.db.delete(activation)
                self.db.flush()

                if self.login_after_activation:
                    login_service = get_login_service(self.request.registry)
                    return login_service.authenticate(self.request, user)
                else:
                    self.request.registry.notify(RegistrationActivatedEvent(self.request, user, activation))
                    return HTTPFound(location=self.after_activate_url)

        return HTTPNotFound()


    def create_forgot_password_request(self, email, location=None) -> Response:
        """Create a new email activation token for a user and produce the following screen.

        * Sets user password reset token

        * Sends out reset password email

        * The existing of user with such email should be validated beforehand

        :raise: CannotResetPasswordException if there is any reason the password cannot be reset. Usually wrong email.
        """

        request = self.request
        dbsession = self.request.dbsession

        user_registry = get_user_registry(request)

        reset_info = user_registry.create_password_reset_token(email)
        if not reset_info:
            raise CannotResetPasswordException("Cannot reset password for email: {}".format(email))
        user, token = reset_info

        link = request.route_url('reset_password', code=token)
        context = dict(link=link, user=user)
        send_templated_mail(request, [email,], "login/email/forgot_password", context=context)

        messages.add(request, msg="Please check your email to continue password reset.", kind='success', msg_id="msg-check-email")

        if not location:
            #: TODO configuration option here probable wrong
            location = get_config_route(request, 'horus.reset_password_redirect')
            assert location

        return HTTPFound(location=location)

    def get_user_for_password_reset_token(self, activation_code: str) -> IUser:
        """Get a user by activation token.

        """
        request = self.request
        user_registry = get_user_registry(request)
        user = user_registry.get_user_by_password_reset_token(activation_code)
        return user

    def reset_password(self, activation_code: str, password: str, location=None) -> Response:
        """Perform actual password reset operations.

        User has following password reset link (GET) or enters the code on a form.
        """
        request = self.request
        user_registry = get_user_registry(request)
        user = user_registry.get_user_by_password_reset_token(activation_code)
        if not user:
            return HTTPNotFound("Activation code not found")

        user_registry.set_password(user, password)

        messages.add(request, msg="The password reset complete. Please sign in with your new password.", kind='success', msg_id="msg-password-reset-complete")
        request.registry.notify(PasswordResetEvent(self.request, user, password))

        location = location or get_config_route(request, 'horus.reset_password_redirect')
        return HTTPFound(location=location)
