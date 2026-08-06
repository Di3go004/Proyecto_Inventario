from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('username', 'get_full_name', 'rol', 'is_active', 'is_staff')
    list_filter = ('rol', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('Rol del sistema', {'fields': ('rol',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Rol del sistema', {'fields': ('rol',)}),
    )
