"""Email templates for authentication workflows."""

from __future__ import annotations


def parent_password_reset_email(*, reset_link: str, expires_minutes: int) -> tuple[str, str]:
    subject = "Réinitialisation de votre mot de passe — Learning Coach AI"
    body = (
        "Bonjour,\n\n"
        "Vous avez demandé la réinitialisation de votre mot de passe Learning Coach AI.\n"
        f"Utilisez ce lien sécurisé (valide {expires_minutes} minutes) :\n\n"
        f"{reset_link}\n\n"
        "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.\n"
        "Pour votre sécurité, ne partagez jamais ce lien.\n"
    )
    return subject, body


def child_password_recovery_requested_email(
    *,
    child_display: str,
    reset_link: str,
    expires_minutes: int,
) -> tuple[str, str]:
    subject = "Réinitialisation du mot de passe élève — Learning Coach AI"
    body = (
        "Bonjour,\n\n"
        "Une demande de réinitialisation de mot de passe a été effectuée pour le compte élève "
        f"« {child_display} ».\n"
        f"Pour définir un nouveau mot de passe, utilisez ce lien (valide {expires_minutes} minutes) :\n\n"
        f"{reset_link}\n\n"
        "Si vous n'êtes pas à l'origine de cette demande, contactez le support et changez votre mot de passe parent.\n"
    )
    return subject, body


def password_changed_notification_email(*, account_label: str) -> tuple[str, str]:
    subject = "Mot de passe modifié — Learning Coach AI"
    body = (
        f"Bonjour,\n\nLe mot de passe du compte « {account_label} » vient d'être modifié.\n"
        "Si vous n'êtes pas à l'origine de ce changement, reconnectez-vous et contactez le support.\n"
    )
    return subject, body
