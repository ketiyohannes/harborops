from django.core.management.base import BaseCommand, CommandError

from core.security_config import validate_app_aes_key_environment


class Command(BaseCommand):
    help = "Validate security-critical environment configuration"

    def handle(self, *args, **options):
        try:
            validate_app_aes_key_environment()
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS("Security configuration is valid."))
