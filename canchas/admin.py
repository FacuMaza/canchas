# canchas/admin.py
from django.contrib import admin
from .models import *
# Importa todos los modelos que quieras que aparezcan en el admin de Django

# Forma más simple de registrar (sin personalización de cómo se ve en el admin)
admin.site.register(Cancha)
admin.site.register(HorarioDisponible)
# Registra los demás modelos que quieras gestionar desde el admin
# Por ejemplo:
# admin.site.register(Reserva)
# admin.site.register(Ingreso)
# admin.site.register(Extra)
# ... y así sucesivamente para todos tus modelos

# Si quieres personalizar cómo se muestra Cancha en el admin (recomendado):
# @admin.register(Cancha)
# class CanchaAdmin(admin.ModelAdmin):
#     list_display = ('nombre', 'tipo_deporte', 'esta_activa', 'ubicacion')
#     list_filter = ('esta_activa', 'tipo_deporte')
#     search_fields = ('nombre', 'descripcion', 'ubicacion')
#     # Agrega aquí cualquier otra personalización que desees para el modelo Cancha en el admin

# Puedes hacer lo mismo para otros modelos importantes, como Reserva:
# @admin.register(Reserva)
# class ReservaAdmin(admin.ModelAdmin):
#     list_display = (
#         '__str__', # Usa el __str__ modificado
#         'cancha',
#         'fecha',
#         'hora_inicio',
#         'estado',
#         'tipo_reserva_origen',
#         'usuario', # Usuario registrado
#         'cliente_nombre', # Cliente web
#         'precio_reserva'
#     )
#     list_filter = ('estado', 'tipo_reserva_origen', 'fecha', 'cancha')
#     search_fields = (
#         'nombre_reserva',
#         'usuario__username',
#         'cliente_nombre',
#         'cliente_email',
#         'cancha__nombre'
#     )
#     fieldsets = (
#         (None, {
#             'fields': ('cancha', 'fecha', 'hora_inicio', 'hora_fin', 'nombre_reserva', 'precio_reserva')
#         }),
#         ('Estado y Origen', {
#             'fields': ('estado', 'tipo_reserva_origen')
#         }),
#         ('Datos del Reservante', {
#             'fields': ('usuario', 'cliente_nombre', 'cliente_email', 'cliente_telefono')
#         }),
#         ('Administración', {
#             'fields': ('notas_internas', 'fecha_creacion'),
#             'classes': ('collapse',)
#         }),
#     )
#     readonly_fields = ('fecha_creacion',)
#     date_hierarchy = 'fecha'
#     ordering = ('-fecha', '-hora_inicio')

# ... y así para otros modelos que necesiten una visualización/edición más detallada en el admin.