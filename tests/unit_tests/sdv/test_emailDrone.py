from flask_mail import Mail
from sdv.emailDrone import (
    mail,
    email_confirmation,
    old_email_confirmation,
    email_passwordreset,
)


def test_email_confirmation():
    with mail.record_messages() as outbox:
        email_confirmation("foo@bar.com", 123, "randomkey")
        assert len(outbox) == 1
        m = outbox[0]
        assert m.subject == "Confirm upload.farm registration"
        assert (
            m.body
            == "Hello!Someone using this email address just signed up for an account on upload.farm. To verify this is correct, please visit: http://upload.farm/verify_email?i=123&t=randomkey If this is in error no action is necessary and you will not hear from us again. Verifying your email address allows us to send you password reset email. Thanks! The upload.farm devs"
        )
        assert (
            m.html
            == '<p>Hello! </p><p>Someone using this email address just signed up for an account on upload.farm. To verify this is correct, please <a href="http://upload.farm/verify_email?i=123&t=randomkey">click here</a>.</p> <p>If this is in error no action is necessary and you will not hear from us again. Verifying your email address allows us to send you password reset email.</p><p>Thanks!<br>The upload.farm devs</p>'
        )


def test_old_email_confirmation():
    with mail.record_messages() as outbox:
        old_email_confirmation("foo@bar.com", 123, "randomkey")
        assert len(outbox) == 1
        m = outbox[0]
        assert m.subject == "Confirm upload.farm registration"
        assert (
            m.body
            == "Hello! Some time ago, someone using this email address signed up for an account on upload.farm. To verify this is correct, please visit: http://upload.farm/verify_email?i=123&t=randomkey If this is in error no action is necessary and you will not hear from us again. Verifying your email address allows us to send you password reset email. Thanks! The upload.farm devs"
        )
        assert (
            m.html
            == '<p>Hello!</p><p>Some time ago, someone using this email address signed up for an account on upload.farm. To verify this is correct, please <a href="http://upload.farm/verify_email?i=123&t=randomkey">click here</a>.</p> <p>If this is in error no action is necessary and you will not hear from us again. Verifying your email address allows us to send you password reset email.</p><p>Thanks!<br>The upload.farm devs</p>'
        )


def test_email_passwordreset():
    with mail.record_messages() as outbox:
        email_passwordreset("foo@bar.com", 123, "randomkey")
        assert len(outbox) == 1
        m = outbox[0]
        assert m.subject == "Reset upload.farm password"
        print(m.body)
        assert (
            m.body
            == "Hello! Someone has requested a password reset for this email address on upload.farm. To reset your password, please visit: http://upload.farm/reset?i=123&t=randomkey If this is in error no action is necessary."
        )
        print(m.html)
        assert (
            m.html
            == '<p>Hello!</p><p>Someone has requested a password reset for this email address on upload.farm. To reset your password, please <a href="http://upload.farm/reset?i=123&t=randomkey">click here</a>.</p> <p>If this is in error no action is necessary.</p>'
        )
