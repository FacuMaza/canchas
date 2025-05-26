from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _ # Para posibles traducciones
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from django.db.models.functions import Coalesce
from django.db.models import Sum
from .models import *
from django.contrib.auth.models import User, Group

class Cancha(models.Model):
    """Representa una cancha deportiva en el sistema."""

    # Opciones para tipo de deporte (puedes añadir más)
    SPORT_CHOICES = [
        ('futbol_5', 'Fútbol 5'),
        ('futbol_7', 'Fútbol 7'),
        ('futbol_11', 'Fútbol 11'),
        ('tenis', 'Tenis'),
        ('padel', 'Pádel'),
        ('basquet', 'Básquetbol'),
        ('voley', 'Vóley'),
        ('otro', 'Otro'),
    ]

    nombre = models.CharField(
        _("Nombre de la Cancha"),
        max_length=100,
        unique=True, # Asegura que no haya canchas con el mismo nombre
        help_text=_("Ej: Cancha Principal, Pista 1 Tenis")
    )
    tipo_deporte = models.CharField(
        _("Tipo de Deporte"),
        max_length=20,
        choices=SPORT_CHOICES,
        default='otro'
    )
    descripcion = models.TextField(
        _("Descripción"),
        blank=True,
        null=True,
        help_text=_("Detalles adicionales como tipo de superficie, si es techada, etc.")
    )
    ubicacion = models.CharField(
        _("Ubicación"),
        max_length=200,
        blank=True,
        null=True,
        help_text=_("Descripción de dónde se encuentra dentro del complejo.")
    )
    esta_activa = models.BooleanField(
        _("Está Activa"),
        default=True,
        help_text=_("Desmarcar si la cancha no está disponible temporalmente (mantenimiento, etc.)")
    )

    class Meta:
        verbose_name = _("Cancha")
        verbose_name_plural = _("Canchas")
        ordering = ['nombre'] # Ordenar por nombre por defecto

    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_deporte_display()})"


class HorarioDisponible(models.Model):
    """Representa un bloque de tiempo en un día específico en que una cancha está disponible."""

    # Opciones para los días de la semana (ISO 8601 standard: Lunes=1, Domingo=7)
    # O Django convention (Lunes=0, Domingo=6) - Usaremos la de Django por consistencia interna
    DAY_CHOICES = [
        (0, _('Lunes')),
        (1, _('Martes')),
        (2, _('Miércoles')),
        (3, _('Jueves')),
        (4, _('Viernes')),
        (5, _('Sábado')),
        (6, _('Domingo')),
    ]

    cancha = models.ForeignKey(
        Cancha,
        on_delete=models.CASCADE, # Si se borra la cancha, se borran sus horarios
        related_name='horarios_disponibles', # Nombre para acceder desde la cancha (cancha.horarios_disponibles.all())
        verbose_name=_("Cancha")
    )
    dia_semana = models.IntegerField(
        _("Día de la Semana"),
        choices=DAY_CHOICES
    )
    hora_inicio = models.TimeField(
        _("Hora de Inicio")
    )
    hora_fin = models.TimeField(
        _("Hora de Fin")
    )

    class Meta:
        verbose_name = _("Horario Disponible")
        verbose_name_plural = _("Horarios Disponibles")
        # Asegura que no haya dos bloques exactamente iguales para la misma cancha en el mismo día
        unique_together = ('cancha', 'dia_semana', 'hora_inicio', 'hora_fin')
        ordering = ['cancha', 'dia_semana', 'hora_inicio'] # Ordenar por cancha, luego día, luego hora

    def __str__(self):
        return f"{self.cancha.nombre} - {self.get_dia_semana_display()}: {self.hora_inicio.strftime('%H:%M')} - {self.hora_fin.strftime('%H:%M')}"

    def clean(self):
        # Validación para asegurar que la hora de inicio sea antes que la hora de fin
        if self.hora_inicio and self.hora_fin and self.hora_inicio >= self.hora_fin:
            raise ValidationError(_('La hora de inicio debe ser anterior a la hora de fin.'))

class Reserva(models.Model):
    ESTADO_CHOICES = [('confirmada', 'Confirmada'), ('pendiente', 'Pendiente'), ('cancelada', 'Cancelada')]
    TIPO_RESERVA_ORIGEN_CHOICES = [('unico', 'Único'), ('mensual', 'Mensual')]

    cancha = models.ForeignKey(Cancha, on_delete=models.CASCADE, related_name='reservas', verbose_name="Cancha")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reservas', verbose_name="Usuario")
    fecha = models.DateField("Fecha de la Reserva")
    hora_inicio = models.TimeField("Hora de Inicio")
    hora_fin = models.TimeField("Hora de Fin")
    estado = models.CharField("Estado", max_length=20, choices=ESTADO_CHOICES, default='confirmada') # Mantenemos confirmada por ahora
    fecha_creacion = models.DateTimeField("Fecha de Creación", auto_now_add=True)
    nombre_reserva = models.CharField("Nombre Reserva", max_length=100, blank=True, null=True)
    tipo_reserva_origen = models.CharField("Tipo Origen", max_length=10, choices=TIPO_RESERVA_ORIGEN_CHOICES, default='unico')
    precio_reserva = models.DecimalField(
        "Precio de la Reserva", max_digits=10, decimal_places=2,
        null=True, blank=True, help_text="Precio cobrado por este turno específico (sin extras)."
    )
    notas_internas = models.TextField("Notas Internas (Admin)", blank=True, null=True)

    class Meta:
        verbose_name = "Reserva"; verbose_name_plural = "Reservas"
        unique_together = ('cancha', 'fecha', 'hora_inicio')
        ordering = ['fecha', 'hora_inicio']

    def __str__(self):
        user_str = self.usuario.username if self.usuario else "Sin usuario"
        tipo_str = f" ({self.get_tipo_reserva_origen_display()})" if hasattr(self, 'get_tipo_reserva_origen_display') else ""
        nombre_str = f" '{self.nombre_reserva}'" if self.nombre_reserva else ""
        precio_str = f" - ${self.precio_reserva}" if self.precio_reserva else ""
        return f"Reserva: {self.cancha.nombre} - {self.fecha.strftime('%Y-%m-%d')} {self.hora_inicio.strftime('%H:%M')}{nombre_str}{tipo_str}{precio_str} ({user_str})"

    # --- MÉTODO SAVE SIN CREACIÓN DE INGRESO ---
    def save(self, *args, **kwargs):
        # Lógica opcional para asignar precio si no se proporcionó
        if self.precio_reserva is None:
             # ¡¡¡IMPORTANTE: Ajusta tu lógica de cálculo de precio aquí!!!
             precio_calculado = Decimal('1500.00') # ¡¡¡REEMPLAZAR ESTE VALOR!!!
             self.precio_reserva = precio_calculado
        # Guarda la reserva normalmente
        super().save(*args, **kwargs)

    # clean() sin cambios necesarios aquí
    def clean(self):
        if self.hora_inicio and self.hora_fin and self.hora_inicio >= self.hora_fin:
             raise ValidationError('La hora de inicio debe ser anterior a la hora de fin.')
        





















    # --- Modelo para Ingresos ---
class Ingreso(models.Model):
    """Registra cualquier entrada de dinero."""
    METODO_PAGO_CHOICES = [
        ('efectivo', 'Efectivo'),
        ('tarjeta_debito', 'Tarjeta de Débito'),
        ('tarjeta_credito', 'Tarjeta de Crédito'),
        ('transferencia', 'Transferencia'),
        ('mercado_pago', 'Mercado Pago'),
        ('otro', 'Otro'),
    ]

    reserva = models.ForeignKey(
        Reserva,
        on_delete=models.SET_NULL,  # Mantener registro de ingreso si se borra reserva
        null=True, blank=True,
        related_name='ingresos_asociados',
        verbose_name=_("Reserva Asociada (Opcional)")
    )
    venta = models.ForeignKey(
        'Venta',
        on_delete=models.SET_NULL,  # Mantener registro de ingreso si se borra venta
        null=True, blank=True,
        related_name='ingresos_asociados',
        verbose_name=_("Venta Asociada (Opcional)")
    )
    fecha = models.DateField(
        _("Fecha del Ingreso"),
        default=timezone.now
    )
    monto = models.DecimalField(
        _("Monto"),
        max_digits=12,
        decimal_places=2
    )
    descripcion = models.CharField(
        _("Descripción"),
        max_length=255,
        help_text=_("Ej: Pago reserva, Venta extra, Abono mensual")
    )
    metodo_pago = models.CharField(
        _("Método de Pago"),
        max_length=20,
        choices=METODO_PAGO_CHOICES,
        blank=True, null=True
    )

    class Meta:
        verbose_name = _("Ingreso")
        verbose_name_plural = _("Ingresos")
        ordering = ['-fecha', '-pk']

    def __str__(self):
        res_info = f" (Reserva #{self.reserva.pk})" if self.reserva else ""
        venta_info = f" (Venta #{self.venta.pk})" if self.venta else ""
        return f"Ingreso: ${self.monto:.2f} - {self.fecha.strftime('%Y-%m-%d')} - {self.descripcion}{res_info}{venta_info}"

class Extra(models.Model):
    """Representa un producto o servicio extra que se puede añadir a una reserva."""
    nombre = models.CharField(
        "Nombre del Extra",
        max_length=100,
        unique=True,
        help_text="Ej: Bebida Isotónica, Alquiler Paleta, Tubo Pelotas"
    )
    descripcion = models.TextField(
        "Descripción",
        blank=True, null=True
    )
    precio_actual = models.DecimalField(
        "Precio Actual",
        max_digits=10,
        decimal_places=2,
        help_text="El precio de venta actual de este extra."
    )
    activo = models.BooleanField(
        "Activo",
        default=True,
        help_text="Indica si este extra está disponible para la venta."
    )
    

    class Meta:
        verbose_name = "Extra"
        verbose_name_plural = "Extras"
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} (${self.precio_actual:.2f})"



 #--- Modelo para Egresos ---
class Egreso(models.Model):
    """Registra cualquier salida de dinero (gasto)."""

    # --- Tus Choices originales ---
    CATEGORIA_EGRESO_CHOICES = [
        ('mantenimiento', 'Mantenimiento'),
        ('servicios', 'Servicios (Luz, Agua, Gas)'),
        ('personal', 'Personal / Sueldos'),
        ('limpieza', 'Limpieza'),
        ('marketing', 'Marketing / Publicidad'),
        ('impuestos', 'Impuestos / Tasas'),
        ('insumos', 'Insumos Deportivos'),
        ('proveedores', 'Proveedores Varios'),
        ('administrativo', 'Gasto Administrativo'),
        ('otro', 'Otro'),
    ]
    # --- Fin Choices ---

    # --- Tus Campos originales ---
    cancha = models.ForeignKey(
        Cancha,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        # Es buena práctica tener related_names únicos si varios FK apuntan al mismo modelo
        # o simplemente para claridad. Ajustado aquí.
        related_name='egresos_asociados_cancha',
        verbose_name="Cancha Asociada (Opcional)"
    )
    reserva = models.ForeignKey(
        Reserva,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='egresos_asociados_reserva', # Ajustado para claridad/unicidad
        verbose_name="Reserva Asociada (Opcional)"
    )
    fecha = models.DateField(
        _("Fecha del Egreso"),
        default=timezone.now # Usar timezone.now como default es correcto
    )
    monto = models.DecimalField(
        _("Monto"),
        max_digits=12,
        decimal_places=2
    )
    descripcion = models.TextField( # TextField permite más texto
        _("Descripción del Gasto")
    )
    categoria = models.CharField(
        _("Categoría"),
        max_length=30, # Asegúrate que sea suficiente para tus claves de choices
        choices=CATEGORIA_EGRESO_CHOICES,
        default='otro'
    )
    # --- Fin Campos originales ---


  
    producto = models.ForeignKey(
        Extra,                      
        on_delete=models.SET_NULL,
        null=True,                  
        blank=True,                 
        related_name='egresos_por_venta',
        verbose_name=_("Producto Vendido (Opcional)")
    )

    metodo_pago = models.CharField(
        _("Método de Pago"),
        max_length=20,
        # Reutilizamos las choices de Ingreso. Asegúrate que Ingreso.METODO_PAGO_CHOICES exista.
        choices=Ingreso.METODO_PAGO_CHOICES,
        blank=True, # Cambia a False si quieres que sea OBLIGATORIO para todos los egresos
        null=True   # Cambia a False si es obligatorio y blank=False
    )


    class Meta:
        verbose_name = _("Egreso")
        verbose_name_plural = _("Egresos")
        ordering = ['-fecha', '-pk'] # Tu ordenación original

    def __str__(self):
        metodo_str = f" ({self.get_metodo_pago_display()})" if self.metodo_pago else ""
        # Hacemos el __str__ un poco más informativo si hay producto
        cancha_info = f" (Cancha: {self.cancha.nombre})" if self.cancha else ""
        reserva_info = f" (Reserva ID: {self.reserva.pk})" if self.reserva else "" # Asumiendo pk es suficiente
        prod_info = f" (Prod: {self.producto.nombre})" if self.producto else ""
        # Acorta la descripción para que no ocupe toda la línea
        desc_corta = (self.descripcion[:40] + '...') if len(self.descripcion) > 40 else self.descripcion

        return (f"{self.fecha.strftime('%d/%m/%y')} - Egreso: ${self.monto:.2f} "
                f"({self.get_categoria_display()}{metodo_str}{prod_info}{cancha_info}{reserva_info}) - {desc_corta}")





class ResumenDiario(models.Model):
    fecha = models.DateField(_("Fecha"), unique=True)
    total_ingresos = models.DecimalField(
        _("Total Ingresos"),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_egresos = models.DecimalField(
        _("Total Egresos"),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_extras = models.DecimalField(
        _("Total Ventas Extras"),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )

    class Meta:
        verbose_name = _("Resumen Diario")
        verbose_name_plural = _("Resúmenes Diarios")
        ordering = ['-fecha']

    def __str__(self):
        return f"Resumen {self.fecha.strftime('%Y-%m-%d')}: Ingresos ${self.total_ingresos}, Egresos ${self.total_egresos}, Extras ${self.total_extras}"

    @property
    def balance(self):
        return self.total_ingresos - self.total_egresos + self.total_extras

# Modelo para resumen mensual
class ResumenMensual(models.Model):
    año = models.IntegerField(_("Año"))
    mes = models.IntegerField(_("Mes"))  # 1 a 12
    total_ingresos = models.DecimalField(
        _("Total Ingresos"),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_egresos = models.DecimalField(
        _("Total Egresos"),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_extras = models.DecimalField(
        _("Total Ventas Extras"),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )

    class Meta:
        verbose_name = _("Resumen Mensual")
        verbose_name_plural = _("Resúmenes Mensuales")
        unique_together = ('año', 'mes')
        ordering = ['-año', '-mes']

    def __str__(self):
        return f"Resumen {self.mes}/{self.año}: Ingresos ${self.total_ingresos}, Egresos ${self.total_egresos}, Extras ${self.total_extras}"

    @property
    def balance(self):
        return self.total_ingresos - self.total_egresos + self.total_extras




##stock
class Stock(models.Model):
    """Representa el inventario disponible de un producto (extra)."""
    
    extra = models.ForeignKey(
        Extra,
        on_delete=models.CASCADE,  # Si se elimina el extra, se elimina su stock
        related_name='stocks',
        verbose_name=_("Producto Extra")
    )
    cantidad = models.PositiveIntegerField(
        _("Cantidad en Stock"),
        default=0,
        help_text=_("Cantidad disponible para la venta.")
    )
    fecha_actualizacion = models.DateTimeField(
        _("Fecha de Última Actualización"),
        auto_now=True
    )

    class Meta:
        verbose_name = _("Stock")
        verbose_name_plural = _("Stocks")
        # Un extra no puede tener más de un registro de stock
        unique_together = ('extra',)
        ordering = ['extra__nombre']

    def __str__(self):
        return f"Stock de {self.extra.nombre}: {self.cantidad} unidades"

    def clean(self):
        """Validar que la cantidad no sea negativa."""
        if self.cantidad < 0:
            raise ValidationError(_('La cantidad en stock no puede ser negativa.'))

    def reducir_stock(self, cantidad):
        """Método para reducir el stock al realizar una venta."""
        if cantidad > self.cantidad:
            raise ValidationError(_(f'No hay suficiente stock de {self.extra.nombre}. Disponible: {self.cantidad}'))
        self.cantidad -= cantidad
        self.save()

    def aumentar_stock(self, cantidad):
        """Método para aumentar el stock al recibir inventario."""
        if cantidad < 0:
            raise ValidationError(_('La cantidad a aumentar no puede ser negativa.'))
        self.cantidad += cantidad
        self.save()


## ventas 

class Venta(models.Model):
    """Registra una venta de productos extras, asociada opcionalmente a una reserva."""

    extra = models.ForeignKey(
        Extra,
        on_delete=models.CASCADE,
        related_name='ventas',
        verbose_name=_("Producto Extra")
    )
    # Hacemos reserva opcional explícitamente (aunque ya lo era con SET_NULL, null=True, blank=True)
    reserva = models.ForeignKey(
        Reserva,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ventas',
        verbose_name=_("Reserva Asociada (Opcional)")
    )
    cantidad = models.PositiveIntegerField(
        _("Cantidad Vendida"),
        help_text=_("Número de unidades vendidas.")
    )
    precio_unitario = models.DecimalField(
        _("Precio Unitario"),
        max_digits=10,
        decimal_places=2,
        help_text=_("Precio del extra en el momento de la venta.")
    )
    fecha_venta = models.DateTimeField(
        _("Fecha de Venta"),
        default=timezone.now
    )
    ingreso = models.ForeignKey(
        Ingreso,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ventas_asociadas',
        verbose_name=_("Ingreso Asociado")
    )
    # --- NUEVO CAMPO ---
    metodo_pago = models.CharField(
        _("Método de Pago"),
        max_length=20,
        choices=Ingreso.METODO_PAGO_CHOICES, # Reutilizamos las choices
        blank=False, null=False, # Hacemos que sea obligatorio para la venta directa
        default='efectivo' # Opcional: poner un default común
    )
    # --- FIN NUEVO CAMPO ---

    class Meta:
        verbose_name = _("Venta")
        verbose_name_plural = _("Ventas")
        ordering = ['-fecha_venta']

    def __str__(self):
        reserva_info = f" (Reserva #{self.reserva.pk})" if self.reserva else ""
        # Añadimos el método de pago al string
        metodo_pago_str = f" ({self.get_metodo_pago_display()})" if self.metodo_pago else ""
        return f"Venta: {self.cantidad} x {self.extra.nombre} a ${self.precio_unitario} - {self.fecha_venta.strftime('%Y-%m-%d %H:%M')}{metodo_pago_str}{reserva_info}"

    def clean(self):
        """Validar que la cantidad y el precio sean positivos."""
        if self.cantidad <= 0:
            raise ValidationError(_('La cantidad vendida debe ser mayor a cero.'))
        # Ojo: precio_unitario se asigna en save, así que esta validación puede no ser útil aquí
        # if self.precio_unitario is not None and self.precio_unitario <= 0:
        #     raise ValidationError(_('El precio unitario debe ser mayor a cero.'))
        # No necesitamos validar metodo_pago aquí si es requerido y tiene choices

    def save(self, *args, **kwargs):
        """Sobreescribir save para generar ingreso, guardar venta, LUEGO reducir stock."""
        is_new = self.pk is None # Verificar si es una venta nueva

        # 1. Asignar precio unitario (si no se ha hecho ya)
        if self.precio_unitario is None and self.extra:
            self.precio_unitario = self.extra.precio_actual

        # --- PASO CLAVE 1: Guardar la Venta PRIMERO ---
        # Esto asegura que la venta tenga un PK si es nueva y guarda el metodo_pago en la Venta
        super().save(*args, **kwargs)
        # ---------------------------------------------------------------------

        ingreso_creado = None # Variable para rastrear si se creó el ingreso

        # 2. Crear ingreso asociado (solo para nuevas ventas y si no existe ya)
        #    Este bloque ahora se ejecuta DESPUÉS de guardar la venta.
        if is_new and not self.ingreso:
            if self.precio_unitario is not None: # Asegurarse que hay precio para calcular total
                total = Decimal(self.cantidad) * self.precio_unitario
                try:
                    # Crear el Ingreso usando el metodo_pago de ESTA venta (self.metodo_pago)
                    ingreso_creado = Ingreso.objects.create(
                        reserva=self.reserva, # Será None si no se asoció una reserva
                        fecha=self.fecha_venta.date(),
                        monto=total,
                        descripcion=f"Venta: {self.cantidad} x {self.extra.nombre}",
                        metodo_pago=self.metodo_pago, # <--- Pasa el método de pago
                        venta=self # Asocia esta Venta con el Ingreso
                    )
                    # Actualizar la venta (que ya existe) para vincularla al ingreso recién creado
                    # Usamos update() para evitar llamar a save() de nuevo y saltar señales/recursión
                    Venta.objects.filter(pk=self.pk).update(ingreso=ingreso_creado)
                    self.ingreso = ingreso_creado # Actualizar también la instancia en memoria

                except Exception as e:
                    # Es importante registrar si la creación del Ingreso falla
                    print(f"Error CRÍTICO al crear Ingreso para Venta {self.pk}: {e}")
                    # Dependiendo de tu lógica, podrías querer borrar la Venta aquí o marcarla como incompleta
                    # Por ahora, solo lo registramos en la consola.
            else:
                 # Este caso es menos probable si 'extra' es obligatorio
                 print(f"Advertencia: No se pudo crear ingreso para Venta {self.pk} porque falta precio_unitario.")

        # --- PASO CLAVE 2: Reducir stock DESPUÉS de guardar Venta y crear Ingreso ---
        # Solo intentamos reducir si la venta es nueva, se creó un ingreso,
        # hay un producto asociado y la cantidad es mayor a cero.
        if is_new and ingreso_creado and self.extra and self.cantidad > 0:
            try:
                # Usar select_for_update es bueno si hay posibilidad de ventas concurrentes
                stock = Stock.objects.select_for_update().get(extra=self.extra)
                # Llamar al método que reduce y guarda el stock.
                # Asegúrate que este método maneje la validación de cantidad.
                stock.reducir_stock(self.cantidad)
            except Stock.DoesNotExist:
                # La venta y el ingreso existen, pero el stock no. ¡Error grave!
                print(f"Error CRÍTICO post-venta: No se encontró stock para {self.extra.nombre} (Venta ID: {self.pk}) para reducir.")
                # Considera añadir un sistema de notificación/log más robusto aquí.
            except ValidationError as e:
                # La venta y el ingreso existen, pero no se pudo reducir stock (ej: insuficiente). ¡Error grave!
                print(f"Error CRÍTICO post-venta: No se pudo reducir stock para {self.extra.nombre} (Venta ID: {self.pk}). Error: {e}")
                # Considera añadir un sistema de notificación/log más robusto aquí.
            except Exception as e_stock:
                 # Otros errores inesperados al interactuar con el stock
                 print(f"Error INESPERADO post-venta al reducir stock para {self.extra.nombre} (Venta ID: {self.pk}). Error: {e_stock}")



class Picadito(models.Model):
    """Representa un evento de juego informal (picadito, amistoso, etc.)."""
    nombre = models.CharField(
        _("Nombre/Descripción del Picadito"),
        max_length=150,
        help_text=_("Ej: 'Fútbol Jueves Noche', 'Amistoso Sábado Tarde'")
    )
    fecha = models.DateField(
        _("Fecha del Picadito"),
        default=timezone.now
    )
    hora_inicio = models.TimeField(
        _("Hora de Inicio (Aprox)"),
        null=True, blank=True
    )
    cancha = models.ForeignKey(
        Cancha,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='picaditos',
        verbose_name=_("Cancha Asociada (Opcional)")
    )
    # Eliminamos el campo 'jugadores' de TextField
    # jugadores = models.TextField(...) # <-- ELIMINAR ESTA LÍNEA

    notas = models.TextField(
        _("Notas Adicionales"),
        blank=True, null=True
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Picadito")
        verbose_name_plural = _("Picaditos")
        ordering = ['-fecha', '-hora_inicio']

    def __str__(self):
        fecha_str = self.fecha.strftime('%d/%m/%Y')
        hora_str = f" {self.hora_inicio.strftime('%H:%M')}" if self.hora_inicio else ""
        cancha_str = f" ({self.cancha.nombre})" if self.cancha else ""
        return f"{self.nombre} - {fecha_str}{hora_str}{cancha_str}"

    @property
    def cantidad_participantes(self):
        """Devuelve el número de participantes asociados."""
        # Accede a la relación inversa definida en ParticipantePicadito
        return self.participantes.count() # 'participantes' es el related_name que definiremos

    @property
    def costo_total_estimado(self):
        """Suma los costos calculados de todos los participantes."""
        return self.participantes.aggregate(total=Coalesce(Sum('costo_calculado'), Decimal('0.00')))['total']


class ParticipantePicadito(models.Model):
    """Representa un jugador en un picadito y los items que consumió."""
    picadito = models.ForeignKey(
        Picadito,
        on_delete=models.CASCADE, # Si se borra el picadito, se borran sus participantes
        related_name='participantes', # Nombre para acceder desde Picadito (picadito.participantes.all())
        verbose_name=_("Picadito")
    )
    nombre_jugador = models.CharField(
        _("Nombre del Jugador"),
        max_length=100
    )
    # Usamos ManyToMany para asociar múltiples Extras (productos) a este participante
    items_consumidos = models.ManyToManyField(
        Extra,
        blank=True, # Puede no haber consumido nada
        verbose_name=_("Items Consumidos")
    )
    items_con_descuento = models.ManyToManyField(
        Extra,
        blank=True,
        
        related_name='participantes_con_descuento',
        verbose_name=_("Items Consumidos con Descuento")
    )
    costo_calculado = models.DecimalField(
        _("Costo Calculado"),
        max_digits=10, decimal_places=2,
        default=Decimal('0.00'),
        help_text=_("Costo total de los items consumidos por este jugador (considerando reglas especiales)")
    )
    costo_cancha = models.DecimalField(
        _("Costo Cancha Asignado"),
        max_digits=10, decimal_places=2,
        default=Decimal('0.00'),
        help_text=_("Monto correspondiente a la cancha asignado a este jugador.")
    )
    fecha_agregado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Participante de Picadito")
        verbose_name_plural = _("Participantes de Picaditos")
        # Evitar duplicados del mismo jugador en el mismo picadito (opcional pero recomendado)
        unique_together = ('picadito', 'nombre_jugador')
        ordering = ['nombre_jugador'] # Ordenar por nombre

    def __str__(self):
        return f"{self.nombre_jugador} en {self.picadito.nombre}"
    
    @property
    def costo_total_participante(self):
        """Devuelve el costo total del participante (items + cancha)."""
        # Asegurarse de que ambos campos no sean None
        costo_items = self.costo_calculado if self.costo_calculado is not None else Decimal('0.00')
        costo_cancha_asignado = self.costo_cancha if self.costo_cancha is not None else Decimal('0.00')
        return costo_items + costo_cancha_asignado
