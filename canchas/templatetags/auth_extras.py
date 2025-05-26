from django import template
from django.contrib.auth.models import Group

register = template.Library()

@register.filter(name='has_group')
def has_group(user, group_name):
    """
    Verifica si un usuario pertenece a un grupo específico.
    Uso en plantilla: {% if user|has_group:"NombreDelGrupo" %}
    """
    # Asegurarse de que el usuario esté autenticado para evitar errores
    # con AnonymousUser que no tiene el manager 'groups'.
    if not user.is_authenticated:
        return False
    try:
        # Intenta obtener el grupo y verificar la pertenencia
        # group = Group.objects.get(name=group_name) # Alternativa menos eficiente
        # return group in user.groups.all()
        # Forma más directa y eficiente:
        return user.groups.filter(name=group_name).exists()
    except Group.DoesNotExist:
        # Si el grupo especificado no existe en la BD, retorna False
        return False

# Puedes añadir más filtros o tags aquí si los necesitas en el futuro