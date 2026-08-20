from django.core.management.base import BaseCommand, CommandError

from usuarios.models import Usuario


class Command(BaseCommand):
    help = (
        'Crea un usuario del sistema con su rol. Ejemplo:\n'
        '  python manage.py crear_usuario ana contabilidad --nombre "Ana Lopez"'
    )

    def add_arguments(self, parser):
        parser.add_argument('username', help='Nombre de usuario para iniciar sesión')
        parser.add_argument(
            'rol',
            choices=[r.value for r in Usuario.Rol],
            help='administrador | operador | contabilidad',
        )
        parser.add_argument('--nombre', default='', help='Nombre completo de la persona')
        parser.add_argument(
            '--password',
            help='Contraseña. Si no se indica, se pide de forma interactiva.',
        )

    def handle(self, *args, **options):
        username = options['username']
        rol = options['rol']

        if Usuario.objects.filter(username=username).exists():
            raise CommandError(f'Ya existe un usuario llamado "{username}".')

        password = options.get('password')
        if not password:
            from getpass import getpass
            password = getpass('Contraseña: ')
            if password != getpass('Repite la contraseña: '):
                raise CommandError('Las contraseñas no coinciden.')
        if len(password) < 8:
            raise CommandError('La contraseña debe tener al menos 8 caracteres.')

        partes = options['nombre'].split(' ', 1)
        usuario = Usuario.objects.create_user(
            username=username,
            password=password,
            rol=rol,
            first_name=partes[0] if partes[0] else '',
            last_name=partes[1] if len(partes) > 1 else '',
        )

        # Solo el administrador entra al panel /admin/ de Django. Operador y
        # contabilidad usan únicamente las pantallas del sistema, así el rol
        # de la aplicación y los permisos de Django no se contradicen.
        if rol == Usuario.Rol.ADMINISTRADOR:
            usuario.is_staff = True
            usuario.save(update_fields=['is_staff'])

        self.stdout.write(self.style.SUCCESS(
            f'Usuario "{username}" creado con rol {usuario.get_rol_display()}.'
        ))
        if rol == Usuario.Rol.CONTABILIDAD:
            self.stdout.write('  Puede consultar todo el sistema, pero no modificar nada.')
        elif rol == Usuario.Rol.OPERADOR:
            self.stdout.write('  Puede registrar movimientos, pero no administrar el catálogo.')
