from django import template
from decimal import Decimal # Importa Decimal si trabajas con precios

register = template.Library() # Necesario para registrar los filtros

@register.filter(name='get_item') # Registra la función como un filtro llamado 'get_item'
def get_item(dictionary, key):
    """
    Permite acceder a un item de un diccionario usando una variable como clave
    en las plantillas de Django.
    Ejemplo: {{ mi_diccionario|get_item:mi_variable_clave }}
    """
    if isinstance(dictionary, dict):
        # Intenta obtener usando la clave como string (más común en plantillas)
        # y como viene originalmente por si acaso.
        return dictionary.get(str(key), dictionary.get(key))
    return None # Devuelve None si no es un diccionario o no encuentra la clave

@register.filter(name='to_decimal') # Filtro adicional útil para precios
def to_decimal(value):
    """Convierte un valor a Decimal."""
    try:
        return Decimal(value)
    except (ValueError, TypeError):
        return None # O devuelve 0.0 si prefieres

# Puedes añadir más filtros personalizados aquí si los necesitas

