"""
Formularios de la pantalla de usuarios (RF-01).

Existe aparte del panel /admin/ de Django a propósito: ese panel muestra
grupos, permisos, is_staff y is_superuser, que acá no se usan (el rol de la
aplicación lo decide todo) y que un administrador no técnico podría cambiar
sin querer y dejarse fuera del sistema.
"""

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .claves import generar_clave
from .models import Usuario


class UsuarioForm(forms.ModelForm):
    """Datos de la persona. La contraseña se maneja en formularios aparte."""

    class Meta:
        model = Usuario
        fields = ['username', 'first_name', 'last_name', 'rol', 'is_active']
        labels = {
            'username': 'Usuario para iniciar sesión',
            'first_name': 'Nombres',
            'last_name': 'Apellidos',
            'rol': 'Rol en el sistema',
            'is_active': 'Puede iniciar sesión',
        }
        help_texts = {
            'username': 'Sin espacios. Es lo que escribe al entrar, p. ej. "ileiva".',
        }

    def __init__(self, *args, editor=None, **kwargs):
        """`editor` es quien está usando la pantalla, para no dejarlo
        quitarse a sí mismo el acceso."""
        super().__init__(*args, **kwargs)
        self.editor = editor
        # En la tablet el teclado capitaliza la primera letra solo, y así fue
        # como se creó un "Karla" que después nadie lograba escribir igual.
        self.fields['username'].widget.attrs.update({
            'autocomplete': 'off',
            'autocapitalize': 'none',
            'autocorrect': 'off',
            'spellcheck': 'false',
        })

    def clean_username(self):
        """
        Se guarda siempre en minúsculas. En tablets y teléfonos el teclado
        pone mayúscula a la primera letra solo, así que un usuario creado
        desde ahí queda como "Karla" y luego nadie acierta a escribirlo
        igual. Con esto, y con el backend que no distingue mayúsculas al
        entrar, deja de importar cómo se escriba.
        """
        username = (self.cleaned_data['username'] or '').strip().lower()

        repetido = Usuario.objects.filter(username__iexact=username)
        if self.instance.pk:
            repetido = repetido.exclude(pk=self.instance.pk)
        if repetido.exists():
            raise ValidationError('Ya existe un usuario con ese nombre.')

        return username

    def _se_esta_editando_a_si_mismo(self):
        return (
            self.editor is not None
            and self.instance.pk is not None
            and self.editor.pk == self.instance.pk
        )

    def clean_rol(self):
        rol = self.cleaned_data['rol']
        if self._se_esta_editando_a_si_mismo() and rol != Usuario.Rol.ADMINISTRADOR:
            raise ValidationError(
                'No puedes quitarte a ti mismo el rol de administrador: '
                'perderías el acceso a esta pantalla. Pídeselo a otro administrador.'
            )
        return rol

    def clean_is_active(self):
        activo = self.cleaned_data['is_active']
        if not activo and self._se_esta_editando_a_si_mismo():
            raise ValidationError('No puedes desactivar tu propio usuario.')
        return activo

    def clean(self):
        datos = super().clean()
        # Que nunca quede el sistema sin nadie que pueda administrarlo.
        deja_de_administrar = (
            self.instance.pk
            and self.instance.rol == Usuario.Rol.ADMINISTRADOR
            and (datos.get('rol') != Usuario.Rol.ADMINISTRADOR or not datos.get('is_active'))
        )
        if deja_de_administrar:
            otros = (
                Usuario.objects
                .filter(rol=Usuario.Rol.ADMINISTRADOR, is_active=True)
                .exclude(pk=self.instance.pk)
                .exists()
            )
            if not otros:
                raise ValidationError(
                    'Es el único administrador activo. Nombra otro antes de '
                    'cambiarle el rol o desactivarlo, o el sistema quedaría '
                    'sin quien pueda administrarlo.'
                )
        return datos


class ClaveMixin(forms.Form):
    """Los dos campos de contraseña, compartidos por crear y por restablecer."""

    generar = forms.BooleanField(
        required=False, initial=True, label='Generar una contraseña segura',
        help_text='Se muestra una sola vez al guardar, para entregársela a la persona.',
    )
    clave = forms.CharField(
        required=False, label='O escribir una contraseña',
        widget=forms.PasswordInput(render_value=False, attrs={'autocomplete': 'new-password'}),
    )

    def clean(self):
        """
        Si la persona escribió una contraseña, esa es la que vale — aunque la
        casilla de generar haya quedado marcada.

        Antes era al revés: la casilla venía marcada por defecto y pisaba en
        silencio lo que se hubiera escrito. El resultado era que alguien
        ponía la contraseña que quería, el sistema guardaba otra al azar, y
        se quedaba sin poder entrar sin entender por qué.
        """
        datos = super().clean()
        escrita = (datos.get('clave') or '').strip()

        if escrita:
            try:
                validate_password(escrita, getattr(self, 'instance', None))
            except ValidationError as error:
                self.add_error('clave', error)
            else:
                datos['clave'] = escrita
                datos['generar'] = False
            return datos

        if datos.get('generar'):
            datos['clave'] = generar_clave()
            return datos

        raise ValidationError('Escribe una contraseña o marca "Generar una contraseña segura".')


class UsuarioNuevoForm(ClaveMixin, UsuarioForm):
    """Crear: datos + contraseña inicial en un solo paso."""

    field_order = ['username', 'first_name', 'last_name', 'rol', 'is_active', 'generar', 'clave']

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.set_password(self.cleaned_data['clave'])
        if commit:
            usuario.save()
        return usuario


class RestablecerClaveForm(ClaveMixin):
    """Cambiar la contraseña de alguien que ya existe."""

    def __init__(self, *args, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance

    def save(self):
        self.instance.set_password(self.cleaned_data['clave'])
        self.instance.save(update_fields=['password'])
        return self.instance
