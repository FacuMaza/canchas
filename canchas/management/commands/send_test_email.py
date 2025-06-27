# tu_app/management/commands/send_test_email.py

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings

class Command(BaseCommand):
    help = 'Envía un correo de prueba para verificar la configuración de SMTP.'

    def handle(self, *args, **options):
        self.stdout.write("Intentando enviar correo de prueba...")
        
        try:
            self.stdout.write(f"HOST: {settings.EMAIL_HOST}")
            self.stdout.write(f"PORT: {settings.EMAIL_PORT}")
            self.stdout.write(f"USER: {settings.EMAIL_HOST_USER}")
            self.stdout.write(f"FROM: {settings.DEFAULT_FROM_EMAIL}")

            send_mail(
                'Prueba de correo desde DigitalOcean (Comando)',
                'Este es un correo de prueba enviado desde un comando de gestión de Django.',
                settings.DEFAULT_FROM_EMAIL,
                ['facundomaza013@gmail.com'],  # Email de destino
                fail_silently=False,
            )

            self.stdout.write(self.style.SUCCESS('¡Correo de prueba enviado exitosamente! Revisa tu bandeja de entrada y el Activity Feed de SendGrid.'))

        except Exception as e:
            self.stderr.write(self.style.ERROR('!!! SE PRODUJO UN ERROR AL ENVIAR EL CORREO !!!'))
            # Imprime la excepción completa para un diagnóstico detallado
            import traceback
            traceback.print_exc()