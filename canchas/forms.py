from datetime import date, datetime
from email.headerregistry import Group
import json
from django import forms
from django.utils.translation import gettext_lazy as _
from .models import *



class CustomUserCreationForm(forms.ModelForm):
    # Campos de contraseña para creación
    password = forms.CharField(widget=forms.PasswordInput, label="Contraseña")
    password_confirm = forms.CharField(widget=forms.PasswordInput, label="Confirmar Contraseña")
    # Campo para seleccionar grupos
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False, # Hazlo opcional si un usuario puede no tener grupo
        label="Roles"
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'groups', 'is_active')
        labels = {
            'is_active': 'Cuenta Activa',
        }

    def clean_password_confirm(self):
        # Validación para que las contraseñas coincidan
        password = self.cleaned_data.get("password")
        password_confirm = self.cleaned_data.get("password_confirm")
        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return password_confirm

    def save(self, commit=True):
        # Guardar el usuario y hashear la contraseña
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
            # Guardar los grupos asignados (necesario después de guardar el usuario)
            self.save_m2m()
        return user


class CustomUserEditForm(forms.ModelForm):
    # Campo para seleccionar/modificar grupos
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Roles"
    )

    class Meta:
        model = User
        # Excluimos la contraseña, se maneja por separado
        fields = ('username', 'first_name', 'last_name', 'email', 'groups', 'is_active', 'is_staff')
        labels = {
            'is_active': 'Cuenta Activa',
            'is_staff': 'Puede acceder al Admin de Django', # Permiso para /admin/
        }












class CanchaForm(forms.ModelForm):
    """Formulario para crear y actualizar Canchas."""
    class Meta:
        model = Cancha
        fields = [
            'nombre',
            'tipo_deporte',
            'descripcion',
            'ubicacion',
            'esta_activa',
        ]
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
        }
        help_texts = {
            'nombre': _('El nombre principal que identifica la cancha.'),
            'esta_activa': _('Indica si la cancha está operativa y puede ser reservada.'),
        }
        labels = {
            'nombre': _('Nombre de la Cancha'),
            'tipo_deporte': _('Deporte Principal'),
            'esta_activa': _('¿Está Activa?'),
        }

class HorarioDisponibleForm(forms.ModelForm):
    """Formulario para crear y actualizar Horarios Disponibles."""

    # Usamos widgets específicos para mejor experiencia de usuario
    hora_inicio = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time', 'step': '1800'}), # step=1800 -> incrementos de 30 min
        label=_("Hora de Inicio")
    )
    hora_fin = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time', 'step': '1800'}),
        label=_("Hora de Fin")
    )

    class Meta:
        model = HorarioDisponible
        fields = [
            'dia_semana',
            'hora_inicio',
            'hora_fin',
            # 'cancha' se asignará automáticamente en la vista, no se muestra en el form.
        ]
        widgets = {
            'dia_semana': forms.Select(choices=HorarioDisponible.DAY_CHOICES),
        }
        labels = {
            'dia_semana': _('Día de la Semana'),
        }

    def clean(self):
        cleaned_data = super().clean()
        hora_inicio = cleaned_data.get("hora_inicio")
        hora_fin = cleaned_data.get("hora_fin")

        if hora_inicio and hora_fin and hora_inicio >= hora_fin:
            raise forms.ValidationError(
                _("La hora de inicio debe ser anterior a la hora de fin.")
            )
        # Aquí podrías añadir validaciones más complejas si necesitas (ej: duración mínima/máxima)
        return cleaned_data


class CobroForm(forms.Form):
    # Podríamos pre-llenar monto basado en la reserva
    monto = forms.DecimalField(
        label="Monto Cobrado",
        max_digits=12,
        decimal_places=2,
        required=True,
        widget=forms.NumberInput(attrs={'step': '0.01'})
    )
    metodo_pago = forms.ChoiceField(
        label="Método de Pago",
        choices=[('', '---------')] + Ingreso.METODO_PAGO_CHOICES, # Añadir opción vacía
        required=False # Hacerlo opcional si quieres
    )
    descripcion_adicional = forms.CharField(
        label="Descripción Adicional (Opcional)",
        required=False,
        widget=forms.Textarea(attrs={'rows': 2})
    )


class ExtraForm(forms.ModelForm):
    class Meta:
        model = Extra
        fields = ['nombre', 'descripcion', 'precio_actual', 'activo']
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
            'precio_actual': forms.NumberInput(attrs={'step': '0.01'}),
        }
        labels = {
            'precio_actual': 'Precio de Venta Actual ($)',
            'activo': '¿Está disponible para la venta?'
        }

class IngresoForm(forms.ModelForm):
    # Opcional: Limitar las reservas a un rango de fechas o canchas
    # reserva = forms.ModelChoiceField(
    #     queryset=Reserva.objects.filter(fecha__gte=date.today() - timedelta(days=30)).order_by('-fecha', '-hora_inicio'),
    #     required=False,
    #     label="Asociar a Reserva (Opcional)"
    # )

    class Meta:
        model = Ingreso
        fields = ['fecha', 'monto', 'descripcion', 'metodo_pago', 'reserva'] # Añadido reserva
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
            'monto': forms.NumberInput(attrs={'step': '0.01'}),
            'descripcion': forms.Textarea(attrs={'rows': 3}),
        }
        labels = { 'monto': 'Monto del Ingreso ($)'}

class EgresoForm(forms.ModelForm):
    class Meta:
        model = Egreso
        fields = ['fecha', 'monto', 'descripcion', 'categoria', 'cancha', 'reserva'] # Añadido cancha y reserva
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
            'monto': forms.NumberInput(attrs={'step': '0.01'}),
            'descripcion': forms.Textarea(attrs={'rows': 4}),
        }
        labels = { 'monto': 'Monto del Egreso ($)'}













class MovimientoRapidoForm(forms.Form):
    # ... (definición de campos: tipo, fecha, monto, etc.) ...
    TIPO_MOVIMIENTO_CHOICES = [
        ('ingreso', 'Ingreso'),
        ('egreso', 'Egreso'),
    ]

    tipo = forms.ChoiceField(
        choices=TIPO_MOVIMIENTO_CHOICES,
        label="Tipo de Movimiento",
        widget=forms.RadioSelect
    )
    fecha = forms.DateField(
        label="Fecha",
        # Usar DateInput para compatibilidad con type="date"
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=True
    )
    monto = forms.DecimalField(
        label="Monto",
        max_digits=12,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'step': '0.01'})
    )
    descripcion = forms.CharField(
        label="Descripción",
        widget=forms.Textarea(attrs={'rows': 3}),
        max_length=255,
        required=False
    )
    metodo_pago = forms.ChoiceField(
        choices=[('', '---------')] + Ingreso.METODO_PAGO_CHOICES,
        required=False, # O False si es opcional
        label="Método de Pago"
    )
    extra = forms.ModelChoiceField(
        queryset=Extra.objects.none(),
        required=False,
        label="Producto (Opcional)",
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    cantidad = forms.IntegerField(
        required=False,
        min_value=1,
        label="Cantidad (si seleccionaste Producto)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '1'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # --- Establecer fecha y atributos del widget ---
        fecha_actual = timezone.now().date()
        # Ya NO usamos self.fields['fecha'].initial
        # self.fields['fecha'].initial = fecha_actual

        # Añadir 'readonly' y establecer 'value' directamente
        self.fields['fecha'].widget.attrs['readonly'] = True
        # IMPORTANTE: El value para <input type="date"> debe ser YYYY-MM-DD
        self.fields['fecha'].widget.attrs['value'] = fecha_actual.strftime('%Y-%m-%d')
        # ---------------------------------------------

        # Código existente para 'extra' y 'data-precios'
        self.fields['extra'].queryset = Extra.objects.filter(
            activo=True,
            stocks__isnull=False
        ).distinct().order_by('nombre')
        try:
            extras_precios = { str(extra.pk): str(extra.precio_actual) for extra in self.fields['extra'].queryset }
            self.fields['extra'].widget.attrs['data-precios'] = json.dumps(extras_precios)
        except Exception as e:
             print(f"Advertencia: No se pudieron cargar datos de Extras para JS: {e}")
             self.fields['extra'].widget.attrs['data-precios'] = '{}'

    # ... (método clean sin cambios) ...
    def clean(self):
        cleaned_data = super().clean()
        tipo = cleaned_data.get('tipo')
        monto = cleaned_data.get('monto')
        extra = cleaned_data.get('extra')
        cantidad = cleaned_data.get('cantidad')
        descripcion = cleaned_data.get('descripcion')

        # Validación cruzada entre extra y cantidad
        if extra and not cantidad:
            self.add_error('cantidad', _('Ingresa la cantidad para el producto seleccionado.'))
        elif cantidad and not extra:
            self.add_error('extra', _('Selecciona un producto para la cantidad ingresada.'))

        # Validación de stock si es egreso con producto
        if tipo == 'egreso' and extra and cantidad:
             try:
                stock_obj = extra.stocks.first()
                if not stock_obj or cantidad > stock_obj.cantidad:
                    disponible = stock_obj.cantidad if stock_obj else 0
                    self.add_error('cantidad', _(f'Stock insuficiente para egreso. Disponible: {disponible}'))
             except AttributeError:
                 self.add_error('extra', _(f'Error al verificar stock para egreso de {extra.nombre}.'))

        # Nueva lógica para Monto y Descripción:
        if extra:
            # Si se seleccionó un producto, la descripción es obligatoria, el monto no.
            if not descripcion:
                self.add_error('descripcion', _('Ingresa una descripción para el producto seleccionado.'))
        else:
            # Si NO se seleccionó producto, el monto y la descripción son obligatorios.
            if not monto or monto <= 0:
                self.add_error('monto', _('Ingresa un monto válido mayor a cero si no seleccionas producto.'))
            if not descripcion:
                self.add_error('descripcion', _('Ingresa una descripción para el movimiento.'))

        # Recuperar la fecha del valor inicial puesto en el widget
        # ya que los campos readonly sí envían su valor al POST.
        # Si por alguna razón no viniera, usamos la fecha actual como fallback.
        if 'fecha' not in cleaned_data:
            # Esto es una salvaguarda, no debería ser necesario con readonly
            cleaned_data['fecha'] = timezone.now().date()
        elif isinstance(cleaned_data['fecha'], str):
             # Si viene como string (puede pasar), convertirla a date
             try:
                 cleaned_data['fecha'] = datetime.strptime(cleaned_data['fecha'], '%Y-%m-%d').date()
             except ValueError:
                 # Si la conversión falla, usar la fecha actual
                 cleaned_data['fecha'] = timezone.now().date()


        # Asegurar que la fecha final sea un objeto date
        if not isinstance(cleaned_data.get('fecha'), date):
             cleaned_data['fecha'] = timezone.now().date()


        return cleaned_data

















class StockForm(forms.ModelForm):
    """Formulario para CARGAR stock de un producto (nuevo o existente)."""

    # Campos para que el usuario ingrese los datos del producto y la cantidad
    extra_nombre = forms.CharField(
        label=_("Nombre del Producto"),
        max_length=100,
        help_text=_("Nombre del producto existente o nuevo.")
        # Ya no es disabled, el usuario debe poder escribirlo
    )
    extra_precio = forms.DecimalField(
        label=_("Precio del Producto (Opcional)"),
        max_digits=10,
        decimal_places=2,
        min_value=0,
        required=False, # Hacerlo opcional, quizás solo quieres añadir stock sin cambiar precio
        help_text=_("Si se especifica, actualizará el precio del producto. Si el producto es nuevo, este será su precio inicial.")
    )
    cantidad_a_agregar = forms.IntegerField(
        label=_("Cantidad a Agregar"), # Nombre consistente con la vista/template
        min_value=1, # Normalmente se agrega al menos 1
        help_text=_("Cantidad de unidades a agregar al stock.")
    )

    class Meta:
        model = Stock
        # Solo incluimos campos del modelo Stock que se llenarán directamente.
        # 'extra' y 'cantidad' se manejarán en el método save.
        # Si 'cantidad' en el modelo Stock representa la cantidad *agregada en este movimiento*,
        # lo incluimos. Si representa el total, lo quitamos y lo calculamos aparte.
        # Asumamos que 'cantidad' es la cantidad de este movimiento.
        fields = ['cantidad']
        # Ocultamos el campo 'cantidad' del formulario directo, ya que usamos 'cantidad_a_agregar'
        widgets = {'cantidad': forms.HiddenInput()}


    def __init__(self, *args, **kwargs):
        # Eliminamos el instance=kwargs.get('instance') temporalmente para evitar error en super
        # instance = kwargs.pop('instance', None) # Podríamos necesitarlo si reutilizamos para UpdateView

        super().__init__(*args, **kwargs) # Llamada al __init__ original

        # Quitamos la lógica que accedía a self.instance.extra, porque en CreateView no existe aún.
        # Los campos 'extra_nombre', 'extra_precio', 'cantidad_a_agregar' son ahora campos normales
        # que el usuario llenará. No necesitan 'initial' basado en una instancia inexistente.

        # Re-establecemos el campo cantidad (del modelo) como no requerido a nivel de formulario,
        # ya que su valor vendrá de 'cantidad_a_agregar' y lo pondremos en save()
        self.fields['cantidad'].required = False


    def clean_extra_nombre(self):
        # Podrías añadir validación extra aquí si es necesario
        # por ejemplo, limpiar espacios en blanco
        return self.cleaned_data.get('extra_nombre', '').strip()

    def clean_cantidad_a_agregar(self):
        cantidad = self.cleaned_data.get('cantidad_a_agregar')
        if cantidad is not None and cantidad <= 0:
             raise forms.ValidationError(_('La cantidad a agregar debe ser positiva.'))
        return cantidad

    # Eliminamos el clean() general anterior que validaba 'cantidad' < 0,
    # ya que ahora validamos 'cantidad_a_agregar' > 0

    def save(self, commit=True):
        """
        Sobreescribir save para encontrar/crear el Extra (producto),
        actualizar su precio si se proporcionó, y crear el registro de Stock.
        """
        # 1. Obtener o crear el producto (Extra)
        nombre_producto = self.cleaned_data['extra_nombre']
        precio_producto = self.cleaned_data.get('extra_precio') # Es opcional

        # Usamos get_or_create para manejar productos nuevos y existentes
        extra, created = Extra.objects.get_or_create(
            nombre=nombre_producto,
            # Defaults solo se usa si el objeto se CREA
            defaults={'precio_actual': precio_producto if precio_producto is not None else 0}
        )

        # Si el producto YA EXISTÍA y se proporcionó un NUEVO precio, lo actualizamos
        if not created and precio_producto is not None:
             if extra.precio_actual != precio_producto: # Evita guardado innecesario
                 extra.precio_actual = precio_producto
                 extra.save() # Guardar el cambio en el producto (Extra)

        # 2. Crear la instancia de Stock (sin guardar aún en DB)
        # `super().save(commit=False)` crea una instancia del modelo Stock
        # con los datos de `Meta.fields` que estén en `cleaned_data` (en este caso, 'cantidad', pero lo vamos a sobreescribir).
        stock_instance = super().save(commit=False)

        # 3. Asignar los valores correctos a la instancia de Stock
        stock_instance.extra = extra # Asignar el producto encontrado o creado
        stock_instance.cantidad = self.cleaned_data['cantidad_a_agregar'] # Asignar la cantidad agregada

        # 4. Guardar la instancia de Stock si commit=True
        if commit:
            stock_instance.save()
            # self.save_m2m() # Solo si tuvieras relaciones ManyToMany

        return stock_instance # Devolver la instancia de Stock creada



class StockEditarForm(forms.ModelForm):
    """Formulario para editar el stock y el precio de un producto."""
    
    extra_nombre = forms.CharField(
        label=_("Nombre del Producto"),
        max_length=100,
        help_text=_("Nombre del producto (no editable)."),
        disabled=True  # Hacerlo no editable
    )
    extra_precio = forms.DecimalField(
        label=_("Precio del Producto"),
        max_digits=10,
        decimal_places=2,
        min_value=0,
        help_text=_("Nuevo precio del producto.")
    )
    cantidad = forms.IntegerField(
        label=_("Cantidad en Stock"),
        min_value=0,
        help_text=_("Nueva cantidad en stock.")
    )

    class Meta:
        model = Stock
        fields = ['cantidad']  # Solo incluimos 'cantidad' del modelo Stock

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Prellenar los campos con los valores actuales
        self.fields['extra_nombre'].initial = self.instance.extra.nombre
        self.fields['extra_precio'].initial = self.instance.extra.precio_actual

    def clean(self):
        cleaned_data = super().clean()
        cantidad = cleaned_data.get('cantidad')

        if cantidad is not None and cantidad < 0:
            self.add_error('cantidad', _('La cantidad en stock no puede ser negativa.'))

        return cleaned_data

    def save(self, commit=True):
        """Sobreescribir save para actualizar el stock y el precio del Extra."""
        stock = super().save(commit=False)
        extra_precio = self.cleaned_data['extra_precio']

        # Actualizar el precio del Extra
        stock.extra.precio_actual = extra_precio
        stock.extra.save()

        # Actualizar la cantidad en stock
        stock.cantidad = self.cleaned_data['cantidad']
        if commit:
            stock.save()

        return stock










class VentaForm(forms.ModelForm):
    metodo_pago = forms.ChoiceField(
        label=_("Método de Pago"),
        choices=Ingreso.METODO_PAGO_CHOICES, # Usa las choices del modelo Ingreso
        required=True, # Lo hacemos requerido para la venta
        widget=forms.Select(attrs={'class': 'form-select'}) # Clase Bootstrap
    )

    class Meta:
        model = Venta
        fields = ['extra', 'cantidad', 'metodo_pago']
        widgets = {
             # Quitamos el 'onchange' de aquí, se maneja en el script de la plantilla
             'extra': forms.Select(attrs={'class': 'form-select'}),
             'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
        }
        labels = {
             'extra': _("Producto"),
             'cantidad': _("Cantidad"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo establece el queryset. Ya no se intenta añadir data-precio aquí.
        self.fields['extra'].queryset = Extra.objects.filter(
            activo=True,
            stocks__isnull=False # Asegura que tenga stock asociado
        ).distinct().order_by('nombre')
        # Django generará las <option> estándar.

    def clean(self):
        cleaned_data = super().clean()
        extra = cleaned_data.get('extra')
        cantidad = cleaned_data.get('cantidad')

        if extra and cantidad:
            try:
                # Verifica el stock usando get() ya que debe haber un registro Stock por Extra
                stock_obj = Stock.objects.get(extra=extra)
                if cantidad > stock_obj.cantidad:
                    self.add_error('cantidad', _(f'No hay suficiente stock. Disponible: {stock_obj.cantidad} unidades.'))
            except Stock.DoesNotExist:
                 # Este error no debería ocurrir si el queryset en __init__ es correcto
                 self.add_error('extra', _(f'Error crítico: No se encontró registro de stock para {extra.nombre}. Contacte al administrador.'))
            except Exception as e: # Captura otros posibles errores
                 self.add_error('extra', _(f'Error al verificar stock ({extra.nombre}): {e}'))

        if cantidad is not None and cantidad <= 0:
            self.add_error('cantidad', _('La cantidad vendida debe ser mayor a cero.'))

        return cleaned_data


class PicaditoForm(forms.ModelForm):
    """Formulario para los datos principales del Picadito."""
    class Meta:
        model = Picadito
        fields = ['nombre'] # Solo el nombre principal
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Fútbol Jueves'}),
        }
        labels = {
            'nombre': _("Nombre/Descripción del Picadito"),
        }



from django.forms import inlineformset_factory, BaseInlineFormSet
class ParticipantePicaditoForm(forms.ModelForm):
    """Formulario para un participante individual dentro del FormSet."""
    # Usar el queryset filtrado como antes
    items_consumidos = forms.ModelMultipleChoiceField(
        queryset=Extra.objects.filter(activo=True).order_by('nombre'),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input item-consumido-check'}), # Clase para JS
        required=False,
        label="Items Consumidos"
    )
    # Campo oculto para los PKs de items con descuento
    items_con_descuento_pks = forms.CharField(
        widget=forms.HiddenInput(attrs={'class': 'items-descuento-pks-hidden'}), # Clase para JS
        required=False
    )
    # Costo cancha como antes
    costo_cancha = forms.DecimalField(
        max_digits=10, decimal_places=2,
        required=False,
        initial=Decimal('0.00'),
        # Clases para JS y estilo
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end costo-cancha-input', 'step': '0.01', 'placeholder': '0.00'}),
        label="Costo Cancha ($)"
    )

    class Meta:
        model = ParticipantePicadito
        # Campos que el usuario llenará directamente + el oculto
        fields = ['nombre_jugador', 'costo_cancha', 'items_consumidos', 'items_con_descuento_pks']
        widgets = {
            'nombre_jugador': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Nombre Jugador'}),
        }
        labels = {
            'nombre_jugador': 'Nombre',
        }

    # __init__ se puede mantener como estaba o simplificar si no añades data-precio aquí

# FormSet como antes
ParticipantePicaditoFormSet = inlineformset_factory(
    Picadito,
    ParticipantePicadito,
    form=ParticipantePicaditoForm,
    extra=10,
    can_delete=True,
    # min_num=1, # Descomentar si es necesario
    # validate_min=True,
)









# forms.py

from django import forms

class PublicClienteReservaForm(forms.Form):
    nombre_cliente = forms.CharField(
        label="Tu Nombre Completo",
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control mb-2', 'placeholder': 'Ej: Juan Pérez'})
    )
    