"""
Cambia la contraseña de un usuario desde la terminal.

  python manage.py cambiar_clave operador --generar
  python manage.py cambiar_clave ana --password "la-que-sea"
  python manage.py cambiar_clave ana            (la pide sin mostrarla)

Existe porque el panel /admin/ solo lo alcanza el administrador, y las
contraseñas hay que poder cambiarlas también cuando alguien se va de la
empresa o se filtra una — sin depender de que el admin pueda entrar.
"""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from usuarios.claves import generar_clave
from usuarios.models import Usuario


class Command(BaseCommand):
    help = 'Cambia la contraseña de un usuario del sistema.'

    def add_arguments(self, parser):
        parser.add_argument('username', help='Usuario al que se le cambia la contraseña')
        parser.add_argument('--password', help='Contraseña nueva')
        parser.add_argument(
            '--generar', action='store_true',
            help='Genera una contraseña fuerte y la muestra una sola vez',
        )

    def handle(self, *args, **options):
        try:
            usuario = Usuario.objects.get(username=options['username'])
        except Usuario.DoesNotExist:
            raise CommandError(f'No existe ningún usuario llamado "{options["username"]}".')

        generada = False
        clave = options.get('password')
        if options['generar']:
            if clave:
                raise CommandError('Usa --password o --generar, no los dos.')
            clave = generar_clave()
            generada = True
        elif not clave:
            from getpass import getpass
            clave = getpass('Contraseña nueva: ')
            if clave != getpass('Repítela: '):
                raise CommandError('Las contraseñas no coinciden.')

        # Las mismas reglas que Django aplica en el resto del sistema (largo
        # mínimo, que no sea solo números, que no se parezca al usuario...).
        try:
            validate_password(clave, usuario)
        except ValidationError as error:
            raise CommandError('Contraseña rechazada:\n  - ' + '\n  - '.join(error.messages))

        usuario.set_password(clave)
        usuario.save(update_fields=['password'])

        self.stdout.write(self.style.SUCCESS(
            f'Contraseña actualizada para "{usuario.username}" ({usuario.get_rol_display()}).'
        ))
        if generada:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(f'    {clave}'))
            self.stdout.write('')
            self.stdout.write('Guardala ahora: no se vuelve a mostrar y no se puede recuperar.')
