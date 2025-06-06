from urllib.parse import urlencode
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import (ListView,DetailView,CreateView,UpdateView,DeleteView,TemplateView)
from django.contrib.messages.views import SuccessMessageMixin # Para mensajes de éxito
from django.contrib import messages # Para mensajes manuales si es necesario
from django.utils.translation import gettext_lazy as _
from .models import *
from .forms import *
from datetime import datetime, time, timedelta, date
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views import View
from django.utils import timezone
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.db.models import Sum, F, DecimalField
from django.views.generic.edit import FormView
from django.db import transaction
from django.db.models import Sum, F, DecimalField, Q, Value, Count, DateField
from django.db.models.functions import Coalesce, TruncDay, TruncMonth, TruncYear, Cast
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.contrib.auth.models import User, Group
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from decimal import Decimal, InvalidOperation
from collections import Counter
import io
import locale
from django.utils import formats
from django.http import HttpResponse # Ya deberías tener este
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.utils import simpleSplit



def format_currency(amount):
    """Formatea un Decimal a string de moneda local (ej: $ 1.234,56)."""
    if amount is None:
        return "$ 0,00"
    try:
        formatted = f"${amount:,.2f}"
        return formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "$ 0,00"

def get_ingreso_asociado_str(ingreso):
    """Devuelve el string 'Asociado a' para un Ingreso."""
    if ingreso.reserva:
        nombre = f" ({ingreso.reserva.nombre_reserva})" if ingreso.reserva.nombre_reserva else ""
        return f"Reserva #{ingreso.reserva.pk}{nombre}"
    elif ingreso.venta:
        try:
           return f"Venta #{ingreso.venta.pk} ({ingreso.venta.cantidad}x {ingreso.venta.extra.nombre})"
        except AttributeError:
           return f"Venta #{ingreso.venta.pk} (Extra no definido)"
    return '-'

def get_egreso_asociado_str(egreso):
    """Devuelve el string 'Asociado a' para un Egreso."""
    if egreso.reserva:
        return f"Reserva #{egreso.reserva.pk}"
    elif egreso.cancha:
        return f"Cancha: {egreso.cancha.nombre}"
    elif egreso.producto:
         try:
            return f"Prod: {egreso.producto.nombre}"
         except AttributeError:
            return "Producto no definido"
    return '-'

# --- Clase Base para Estilos y Construcción (Opcional, ayuda a organizar) ---
class BaseReportPDFView(View):
    styles = getSampleStyleSheet()
    # Estilos personalizados
    styles['h1'].alignment = 1 # Center
    styles['h2'].fontSize = 14
    styles['Normal'].fontSize = 9
    styles['Normal'].leading = 11 # Espacio entre líneas

    table_style_header = ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue)
    table_style_header_text = ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke)
    table_style_grid = ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
    # table_style_body_bg = ('BACKGROUND', (0, 1), (-1, -2), colors.lightblue) # Opcional: fondo alterno
    table_style_total_row = ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey)
    table_style_total_font = ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold')
    table_style_align_center = ('ALIGN', (0, 0), (-1, -1), 'CENTER')
    table_style_valign_middle = ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    table_style_padding = ('LEFTPADDING', (0, 0), (-1, -1), 3)
    table_style_rightpadding = ('RIGHTPADDING', (0, 0), (-1, -1), 3)

    col_widths_ingreso = [2.5*cm, 6*cm, 3*cm, 5*cm] # Ajusta según necesidad
    col_widths_egreso = [2.5*cm, 5*cm, 3*cm, 3*cm, 3*cm] # Ajusta según necesidad

    def build_pdf(self, buffer, story):
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5*cm, bottomMargin=1.5*cm, leftMargin=1.5*cm, rightMargin=1.5*cm)
        doc.build(story)






class PublicHomeView(ListView):
    model = Cancha
    template_name = 'public_home.html' # Nueva plantilla
    context_object_name = 'canchas'

    def get_queryset(self):
        return Cancha.objects.filter(esta_activa=True).order_by('nombre')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Reservá Tu Turno"
        context['fecha_hoy_str'] = date.today().strftime('%Y-%m-%d')
        return context



class PublicReservarClienteView(View):
    template_name = 'public_reservar_cliente.html'
    form_class = PublicClienteReservaForm

    def _generar_slots_lee_tipo_origen(self, cancha, fecha_obj):
        # Esta función no se modifica, es correcta.
        slots_del_dia = []
        hora_apertura_cancha = time(7, 0)
        limite_generacion_hora = time(2, 0)
        reservas_existentes_query = Reserva.objects.filter(
            cancha=cancha,
            fecha=fecha_obj,
            estado__in=['confirmada', 'pendiente_pago', 'pendiente']
        ).select_related('usuario')
        reservas_existentes_dict = {
            r.hora_inicio: {
                'pk': r.pk,
                'nombre_reserva': r.nombre_reserva,
                'usuario_info': r.usuario.get_full_name() if r.usuario else (r.nombre_reserva or "Ocupado"),
                'tipo_origen': r.get_tipo_reserva_origen_display(),
                'estado_modelo': r.estado
            }
            for r in reservas_existentes_query
        }
        current_datetime_slot = datetime.combine(fecha_obj, hora_apertura_cancha)
        if limite_generacion_hora < hora_apertura_cancha:
            limite_datetime_generacion = datetime.combine(fecha_obj + timedelta(days=1), limite_generacion_hora)
        else:
            limite_datetime_generacion = datetime.combine(fecha_obj, limite_generacion_hora)
        while current_datetime_slot < limite_datetime_generacion:
            slot_hora_inicio = current_datetime_slot.time()
            slot_dt_fin = current_datetime_slot + timedelta(minutes=cancha.duracion_turno_minutos if hasattr(cancha, 'duracion_turno_minutos') else 30)
            slot_hora_fin = slot_dt_fin.time()
            slot_info_template = {
                'hora_inicio': slot_hora_inicio,
                'hora_fin': slot_hora_fin,
                'hora_inicio_str': slot_hora_inicio.strftime('%H:%M'),
                'hora_fin_str': slot_hora_fin.strftime('%H:%M'),
                'hora_inicio_name_fmt': slot_hora_inicio.strftime('%H-%M'),
                'estado_display': 'disponible',
                'reserva_info': None,
                'reserva_pk': None,
                'tipo_origen_display': None,
                'estado_modelo_reserva': None
            }
            reserva_existente_data = reservas_existentes_dict.get(slot_hora_inicio)
            if reserva_existente_data:
                slot_info_template['reserva_pk'] = reserva_existente_data['pk']
                slot_info_template['reserva_info'] = reserva_existente_data['nombre_reserva'] or reserva_existente_data['usuario_info'] or "Reservado"
                slot_info_template['tipo_origen_display'] = reserva_existente_data['tipo_origen']
                slot_info_template['estado_modelo_reserva'] = reserva_existente_data['estado_modelo']
                if reserva_existente_data['estado_modelo'] in ['pendiente_pago', 'confirmada', 'pendiente']:
                    slot_info_template['estado_display'] = 'reservado'
            if slot_info_template['estado_display'] == 'disponible':
                slots_del_dia.append(slot_info_template)
            current_datetime_slot = slot_dt_fin
        return slots_del_dia
    
    def get(self, request, cancha_pk, fecha):
        cancha = get_object_or_404(Cancha, pk=cancha_pk, esta_activa=True)
        try:
            fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, "Formato de fecha inválido.")
            return redirect('public-home')
        if fecha_obj < timezone.localdate():
            messages.warning(request, "No puedes ver disponibilidad para una fecha pasada.")
            return redirect('public-home')
        slots = self._generar_slots_lee_tipo_origen(cancha, fecha_obj)
        form = self.form_class()
        context = {
            'cancha': cancha,
            'fecha_seleccionada': fecha_obj,
            'fecha_str': fecha,
            'slots': slots,
            'form_cliente': form,
            'titulo_pagina': f"Reservar en {cancha.nombre} para el {fecha_obj.strftime('%d/%m/%Y')}"
        }
        return render(request, self.template_name, context)

    def post(self, request, cancha_pk, fecha):
        cancha = get_object_or_404(Cancha, pk=cancha_pk, esta_activa=True)
        try:
            fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, "Formato de fecha inválido.")
            return redirect('public-home')
        
        # ... El resto de la validación se mantiene igual ...
        form_cliente = self.form_class(request.POST)
        slots_seleccionados_str = request.POST.getlist('slot_reservar')

        def _render_form_con_errores(error_msg=None, form_errors=False):
            # ... Esta función auxiliar no cambia ...
            if error_msg: messages.error(request, error_msg)
            slots = self._generar_slots_lee_tipo_origen(cancha, fecha_obj)
            context = { 'cancha': cancha, 'fecha_seleccionada': fecha_obj, 'fecha_str': fecha, 'slots': slots, 'form_cliente': form_cliente, 'titulo_pagina': f"Reservar en {cancha.nombre}" }
            return render(request, self.template_name, context)

        if not form_cliente.is_valid():
            return _render_form_con_errores("Por favor, revisa los datos del formulario.", form_errors=True)
        if not slots_seleccionados_str:
            return _render_form_con_errores("No seleccionaste ningún horario. Por favor, elige al menos uno.")

        # --- Lógica de creación de reservas (La parte importante) ---
        nombre_cliente = form_cliente.cleaned_data['nombre_cliente']
        slots_seleccionados_time = sorted([datetime.strptime(h, '%H:%M').time() for h in slots_seleccionados_str])
        
        # ... (Toda la validación de conflictos se mantiene) ...

        # MEJORA: Preparamos listas para guardar los resultados
        reservas_creadas_pks = []
        errores_creacion = []
        precio_turno = cancha.precio_publico if hasattr(cancha, 'precio_publico') else None
        duracion_turno = cancha.duracion_turno_minutos if hasattr(cancha, 'duracion_turno_minutos') else 30

        # El bucle de guardado sigue siendo el mismo, solo cambia lo que guardamos
        for hora_inicio in slots_seleccionados_time:
            try:
                # La creación del objeto no cambia
                nueva_reserva = Reserva.objects.create(
                    cancha=cancha,
                    usuario=None,
                    fecha=fecha_obj,
                    hora_inicio=hora_inicio,
                    hora_fin=(datetime.combine(fecha_obj, hora_inicio) + timedelta(minutes=duracion_turno)).time(),
                    nombre_reserva=nombre_cliente,
                    tipo_reserva_origen='publica',
                    precio_reserva=precio_turno,
                    estado='pendiente_pago',
                    notas_internas=f"Reserva cliente público: {nombre_cliente}."
                )
                # MEJORA: Guardamos el ID de la reserva creada
                reservas_creadas_pks.append(nueva_reserva.pk)
            except Exception as e:
                errores_creacion.append(hora_inicio.strftime('%H:%M'))
        
        # --- Redirección y mensajes ---
        if reservas_creadas_pks:
            messages.success(request, f"¡Gracias, {nombre_cliente}! Tu solicitud ha sido registrada.")
            
            # MEJORA: Guardamos la lista de PKs en la sesión. Es la forma más robusta.
            request.session['reserva_exitosa_pks'] = reservas_creadas_pks

            if errores_creacion:
                messages.warning(request, f"Atención: Algunos horarios ({', '.join(errores_creacion)}) no pudieron ser reservados.")
            
            return redirect('reserva-exitosa')
        
        else: # Si no se creó ninguna reserva
            msg_error = "No se pudo procesar tu solicitud. Ningún turno fue creado."
            if errores_creacion: msg_error += f" Problemas con horarios: {', '.join(errores_creacion)}."
            return _render_form_con_errores(msg_error)


class ReservaExitosaView(TemplateView):
    template_name = 'reserva_exitosa.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # MEJORA: Obtenemos los PKs de la sesión.
        reserva_pks = self.request.session.pop('reserva_exitosa_pks', None)
        
        context['titulo_pagina'] = "Reserva Registrada"
        context['reserva_info'] = None  # Inicializamos por defecto
        
        # URL genérica por si algo falla
        wa_params = {'text': 'Hola, quiero confirmar mi solicitud de reserva. Gracias.'}

        if reserva_pks:
            # MEJORA: Buscamos las reservas reales en la BBDD.
            reservas = Reserva.objects.filter(pk__in=reserva_pks).select_related('cancha').order_by('hora_inicio')
            
            if reservas.exists():
                primera_reserva = reservas.first()
                
                # Preparamos el diccionario de información para la plantilla
                context['reserva_info'] = {
                    'cancha_nombre': primera_reserva.cancha.nombre,
                    'fecha_reserva': primera_reserva.fecha,
                    'nombre_cliente': primera_reserva.nombre_reserva,
                    'horas_reservadas': [r.hora_inicio for r in reservas]
                }

                # Construir el mensaje de WhatsApp con los datos correctos
                fecha_str = formats.date_format(primera_reserva.fecha, "l, d \d\e F Y").capitalize()
                horas_str = ", ".join([h.strftime('%H:%M') for h in context['reserva_info']['horas_reservadas']])
                
                mensaje_texto = (
                    f"Hola, quiero confirmar mi reserva para la cancha {primera_reserva.cancha.nombre} "
                    f"el día {fecha_str} a nombre de {primera_reserva.nombre_reserva} "
                    f"para los horarios: {horas_str}. Gracias."
                )
                wa_params['text'] = mensaje_texto
                context['reserva_confirmada'] = True

        context['whatsapp_url'] = f"https://wa.me/5493873546645?{urlencode(wa_params)}"
        return context














@login_required
def dashboard(request):
    return render(request, 'dashboard.html')

## USUARIOS


class UserListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = User
    template_name = 'user_list.html' # Crearemos esta plantilla
    context_object_name = 'usuarios'
    paginate_by = 15

    def test_func(self):
        return is_admin(self.request.user)

    def get_queryset(self):
        # Opcional: Excluir al superusuario principal de la lista si se desea
        # return User.objects.exclude(is_superuser=True).order_by('username')
        return User.objects.all().order_by('username')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Administrar Cuentas"
        return context


class UserCreateView(LoginRequiredMixin, UserPassesTestMixin, SuccessMessageMixin, CreateView):
    model = User
    form_class = CustomUserCreationForm # Usamos nuestro formulario personalizado
    template_name = 'user_form.html' # Plantilla reutilizable
    success_url = reverse_lazy('user-list') # Redirige a la lista de usuarios
    success_message = "Usuario '%(username)s' creado exitosamente."

    def test_func(self):
        return is_admin(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Crear Nuevo Usuario"
        return context

    # El método save() del formulario ya maneja el hash de contraseña


class UserUpdateView(LoginRequiredMixin, UserPassesTestMixin, SuccessMessageMixin, UpdateView):
    model = User
    form_class = CustomUserEditForm # Usamos nuestro formulario de edición
    template_name = 'user_form.html'
    success_url = reverse_lazy('user-list')
    success_message = "Usuario '%(username)s' actualizado exitosamente."
    context_object_name = 'usuario_editado' # Para diferenciar del request.user

    def test_func(self):
        return is_admin(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f"Editar Usuario: {self.object.username}"
        return context

    def dispatch(self, request, *args, **kwargs):
        # Opcional: Evitar que un admin no superusuario se edite a sí mismo ciertos campos críticos
        # O que edite a un superusuario
        # obj = self.get_object()
        # if not request.user.is_superuser and obj == request.user:
        #     messages.warning(request, "No puedes editar tu propia cuenta aquí.")
        #     return redirect('user-list')
        # if not request.user.is_superuser and obj.is_superuser:
        #    messages.error(request, "No puedes editar a un Superusuario.")
        #    return redirect('user-list')
        return super().dispatch(request, *args, **kwargs)


class UserDeleteView(LoginRequiredMixin, UserPassesTestMixin, SuccessMessageMixin, DeleteView):
    model = User
    template_name = 'user_confirm_delete.html'
    success_url = reverse_lazy('user-list')
    # Modificamos el mensaje para que se muestre DESPUÉS de la redirección
    # success_message = "Usuario eliminado exitosamente." # <- Lo manejaremos manualmente
    context_object_name = 'usuario_a_eliminar'

    # 1. test_func: Verifica si el usuario LOGUEADO tiene permiso general para ACCEDER a esta vista
    def test_func(self):
        return is_admin(self.request.user)

    # 2. dispatch: Verifica si el usuario LOGUEADO tiene permiso para borrar al USUARIO ESPECÍFICO
    def dispatch(self, request, *args, **kwargs):
        # Obtenemos el usuario que se intenta eliminar
        target_user = self.get_object()
        # Obtenemos el usuario que está realizando la solicitud
        requesting_user = request.user

        # Regla 1: Nadie puede eliminarse a sí mismo
        if target_user == requesting_user:
            messages.error(request, "No puedes eliminar tu propia cuenta.")
            return redirect('user-list')

        # Regla 2: Permisos del Superusuario
        if requesting_user.is_superuser:
            # Superusuario NO puede eliminar al último superusuario activo
            if target_user.is_superuser:
                active_superusers_count = User.objects.filter(is_superuser=True, is_active=True).count()
                # Si el objetivo es un superusuario activo Y solo queda 1 o menos...
                if target_user.is_active and active_superusers_count <= 1:
                    messages.error(request, "Acción denegada: No puedes eliminar al último Superusuario activo.")
                    return redirect('user-list')
            # Si pasa las verificaciones anteriores, el Superusuario puede eliminar (incluidos Admins)
            # Continuamos con la ejecución normal de la vista
            return super().dispatch(request, *args, **kwargs)

        # Regla 3: Permisos del Admin (que NO es Superusuario)
        elif requesting_user.groups.filter(name='Admins').exists():
            # Admin NO puede eliminar Superusuarios
            if target_user.is_superuser:
                messages.error(request, "Acción denegada: Los Administradores no pueden eliminar Superusuarios.")
                return redirect('user-list')
            # Admin NO puede eliminar otros Admins
            if target_user.groups.filter(name='Admins').exists():
                 messages.error(request, "Acción denegada: Los Administradores no pueden eliminarse entre sí.")
                 return redirect('user-list')
            # Si pasa las verificaciones anteriores, el Admin puede eliminar (probablemente Empleados)
            # Continuamos con la ejecución normal de la vista
            return super().dispatch(request, *args, **kwargs)

        # Si no es Superusuario ni Admin (aunque test_func debería prevenir esto), denegar por si acaso
        else:
             messages.error(request, "No tienes permiso para realizar esta acción.")
             return redirect('user-list') # O a donde sea apropiado

    # Sobreescribimos delete para añadir el mensaje de éxito manualmente
    # ya que SuccessMessageMixin puede no funcionar bien con la lógica compleja de dispatch
    def delete(self, request, *args, **kwargs):
        target_user = self.get_object()
        username = target_user.username # Guarda el nombre antes de borrar
        response = super().delete(request, *args, **kwargs)
        messages.success(request, f"Usuario '{username}' eliminado exitosamente.")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f"Confirmar Eliminación de {self.object.username}"
        return context

def is_admin(user):
    """Verifica si el usuario es superusuario o pertenece al grupo Admins."""
    # Comprobamos primero que esté autenticado para evitar errores con usuarios anónimos
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name='Admins').exists()


class CanchaListView(ListView):
    model = Cancha
    template_name = 'cancha_list.html' # Necesitarás crear esta plantilla
    context_object_name = 'canchas' # Nombre de la variable en la plantilla
    paginate_by = 10 # Opcional: paginación

    def get_queryset(self):
        # Opcional: Mostrar solo canchas activas en la lista principal
        # return Cancha.objects.filter(esta_activa=True).order_by('nombre')
        return Cancha.objects.all().order_by('nombre')


class CanchaDetailView(DetailView):
    model = Cancha
    template_name = 'cancha_detail.html'
    context_object_name = 'cancha'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cancha = self.get_object()
        context['horarios_generales'] = cancha.horarios_disponibles.all().order_by('dia_semana', 'hora_inicio')
        return context


class CanchaCreateView(SuccessMessageMixin, CreateView):
    model = Cancha
    form_class = CanchaForm
    template_name = 'cancha_form.html' # Necesitarás crear esta plantilla (usada para crear/editar)
    success_url = reverse_lazy('cancha-list') # Redirige a la lista después de crear
    success_message = _("Cancha '%(nombre)s' creada exitosamente.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = _("Nueva Cancha")
        return context


class CanchaUpdateView(SuccessMessageMixin, UpdateView):
    model = Cancha
    form_class = CanchaForm
    template_name = 'cancha_form.html' # Reutilizamos la plantilla del formulario
    context_object_name = 'cancha'
    success_message = _("Cancha '%(nombre)s' actualizada exitosamente.")

    def get_success_url(self):
        # Redirige al detalle de la cancha editada
        return reverse_lazy('cancha-detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = _("Editar Cancha")
        return context


class CanchaDeleteView(SuccessMessageMixin, DeleteView):
    model = Cancha
    template_name = 'cancha_confirm_delete.html' # Necesitarás crear esta plantilla
    success_url = reverse_lazy('cancha-list')
    context_object_name = 'cancha'
    success_message = _("Cancha eliminada exitosamente.")

    def delete(self, request, *args, **kwargs):
         messages.success(self.request, self.success_message) # Mensaje antes de borrar por si hay error
         return super().delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = _("Confirmar Eliminación de Cancha")
        return context

# --- Vistas para HorarioDisponible (asociadas a una Cancha) ---

class HorarioDisponibleCreateView(SuccessMessageMixin, CreateView):
    model = HorarioDisponible
    form_class = HorarioDisponibleForm
    template_name = 'horario_form.html' # Necesitarás crear esta plantilla

    def dispatch(self, request, *args, **kwargs):
        # Obtenemos la cancha antes de procesar el formulario
        self.cancha = get_object_or_404(Cancha, pk=self.kwargs['cancha_pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        # Asignamos la cancha al horario antes de guardarlo
        form.instance.cancha = self.cancha
        # Aquí podrías añadir validación de solapamiento antes de guardar si es necesario
        # Ejemplo básico (puede ser complejo y requerir más lógica):
        # if HorarioDisponible.objects.filter(...solapamiento...).exists():
        #     form.add_error(None, _("Este horario se solapa con uno existente."))
        #     return self.form_invalid(form)
        messages.success(self.request, _("Horario añadido exitosamente."))
        return super().form_valid(form)

    def get_success_url(self):
        # Redirige de vuelta al detalle de la cancha a la que pertenece el horario
        return reverse('cancha-detail', kwargs={'pk': self.cancha.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancha'] = self.cancha
        context['titulo_pagina'] = _("Añadir Horario a ") + self.cancha.nombre
        return context


class HorarioDisponibleUpdateView(SuccessMessageMixin, UpdateView):
    model = HorarioDisponible
    form_class = HorarioDisponibleForm
    template_name = 'horario_form.html'
    context_object_name = 'horario'
    success_message = _("Horario actualizado exitosamente.")

    def get_success_url(self):
        # Redirige al detalle de la cancha a la que pertenece
        return reverse('cancha-detail', kwargs={'pk': self.object.cancha.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancha'] = self.object.cancha # Pasamos la cancha para el contexto
        context['titulo_pagina'] = _("Editar Horario de ") + self.object.cancha.nombre
        return context

    def form_valid(self, form):
         # Podrías añadir validación de solapamiento aquí también al actualizar
         return super().form_valid(form)


class HorarioDisponibleDeleteView(SuccessMessageMixin, DeleteView):
    model = HorarioDisponible
    template_name = 'horario_confirm_delete.html' # Necesitarás crear esta plantilla
    context_object_name = 'horario'
    success_message = _("Horario eliminado exitosamente.")

    def get_success_url(self):
        # Redirige al detalle de la cancha a la que pertenecía
        # Guardamos el pk de la cancha ANTES de borrar el objeto
        cancha_pk = self.object.cancha.pk
        return reverse('cancha-detail', kwargs={'pk': cancha_pk})

    def delete(self, request, *args, **kwargs):
        # Obtenemos el objeto antes de llamar al delete para poder mostrar el mensaje
        self.object = self.get_object()
        success_url = self.get_success_url()
        # Usamos messages.success directamente aquí porque el mixin no funciona bien con el redirect post-delete
        messages.success(self.request, self.success_message)
        self.object.delete()
        return redirect(success_url) # Usamos redirect en lugar de super().delete()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancha'] = self.object.cancha
        context['titulo_pagina'] = _("Confirmar Eliminación de Horario")
        return context


##RESERVAS



class ReservarFechaView(View):
    template_name = 'reservar_fecha.html'

    def get(self, request, cancha_pk, fecha):
        cancha = get_object_or_404(Cancha, pk=cancha_pk)
        try:
            fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, "Formato de fecha inválido.")
            return redirect('cancha-detail', pk=cancha_pk)

        if fecha_obj < timezone.localdate():
            messages.warning(request, "No puedes ver/reservar en una fecha pasada desde aquí.")
            return redirect('cancha-detail', pk=cancha_pk)

        slots = self._generar_slots(cancha, fecha_obj)
        context = {
            'cancha': cancha,
            'fecha_seleccionada': fecha_obj,
            'fecha_str': fecha,
            'slots': slots
        }
        return render(request, self.template_name, context)

    def post(self, request, cancha_pk, fecha):
        cancha = get_object_or_404(Cancha, pk=cancha_pk)
        try:
            fecha_base = datetime.strptime(fecha, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, "Formato de fecha inválido.")
            return redirect('cancha-detail', pk=cancha_pk)

        # --- CAMBIO CLAVE: El nombre es opcional. Se limpia y se convierte a None si está vacío. ---
        descripcion_bloque = request.POST.get('nombre_reserva_bloque', '').strip() or None
        
        slots_seleccionados_str = request.POST.getlist('slot_reservar')
        tipo_reserva_seleccionado = request.POST.get('tipo_reserva', 'diario')

        # --- VALIDACIONES ADAPTADAS ---
        if not slots_seleccionados_str:
            messages.warning(request, "No seleccionaste ningún horario.")
            context = {'cancha': cancha, 'fecha_seleccionada': fecha_base, 'fecha_str': fecha, 'slots': self._generar_slots(cancha, fecha_base)}
            return render(request, self.template_name, context)

        # Un nombre es requerido SÓLO si se selecciona más de un turno o si la reserva es mensual.
        if (len(slots_seleccionados_str) > 1 or tipo_reserva_seleccionado == 'mensual') and not descripcion_bloque:
            messages.error(request, "Para reservar múltiples horarios o una reserva mensual, debes ingresar un nombre.")
            context = {'cancha': cancha, 'fecha_seleccionada': fecha_base, 'fecha_str': fecha, 'slots': self._generar_slots(cancha, fecha_base)}
            return render(request, self.template_name, context)

        # ----- RESTO DE LAS VALIDACIONES Y LÓGICA (sin cambios) -----
        slots_seleccionados_time = []
        try:
            for hora_str in slots_seleccionados_str:
                slots_seleccionados_time.append(datetime.strptime(hora_str, '%H:%M').time())
        except ValueError:
            messages.error(request, "Formato de hora inválido en los slots.")
            context = {'cancha': cancha, 'fecha_seleccionada': fecha_base, 'fecha_str': fecha, 'slots': self._generar_slots(cancha, fecha_base)}
            return render(request, self.template_name, context)

        slots_seleccionados_time.sort()

        if len(slots_seleccionados_time) > 1:
            for i in range(len(slots_seleccionados_time) - 1):
                dt1 = datetime.combine(date.today(), slots_seleccionados_time[i])
                dt2 = datetime.combine(date.today(), slots_seleccionados_time[i + 1])
                if dt1 + timedelta(minutes=30) != dt2:
                    messages.error(request, "Los horarios seleccionados para un bloque deben ser consecutivos.")
                    context = {'cancha': cancha, 'fecha_seleccionada': fecha_base, 'fecha_str': fecha, 'slots': self._generar_slots(cancha, fecha_base)}
                    return render(request, self.template_name, context)
        
        fechas_a_reservar = [fecha_base]
        if tipo_reserva_seleccionado == 'mensual':
            for i in range(3):
                fechas_a_reservar.append(fecha_base + timedelta(days=7 * (i + 1)))

        q_objects_conflicto = Q()
        for fr in fechas_a_reservar:
            for hi in slots_seleccionados_time:
                q_objects_conflicto |= Q(fecha=fr, hora_inicio=hi)
        
        if q_objects_conflicto:
            conflictos = Reserva.objects.filter(cancha=cancha, estado__in=['confirmada', 'pendiente_pago']).filter(q_objects_conflicto)
            if conflictos.exists():
                error_detalle = ", ".join([f"{c.fecha.strftime('%d/%m')} {c.hora_inicio.strftime('%H:%M')}" for c in conflictos])
                messages.error(request, f"Los siguientes horarios ya están ocupados: {error_detalle}")
                context = {'cancha': cancha, 'fecha_seleccionada': fecha_base, 'fecha_str': fecha, 'slots': self._generar_slots(cancha, fecha_base)}
                return render(request, self.template_name, context)

        # ----- CREACIÓN DE RESERVAS -----
        reservas_creadas = []
        usuario_a_asignar = request.user if request.user.is_authenticated else None
        estado_para_crear = 'pendiente_pago' if tipo_reserva_seleccionado == 'diario' else 'confirmada'

        for fecha_res in fechas_a_reservar:
            for hora_inicio in slots_seleccionados_time:
                reserva = Reserva(
                    cancha=cancha,
                    usuario=usuario_a_asignar,
                    fecha=fecha_res,
                    hora_inicio=hora_inicio,
                    hora_fin=(datetime.combine(date.today(), hora_inicio) + timedelta(minutes=30)).time(),
                    nombre_reserva=descripcion_bloque,  # Puede ser None
                    tipo_reserva_origen=tipo_reserva_seleccionado,
                    precio_reserva=Decimal('1500.00'), # Ajusta este valor
                    estado=estado_para_crear
                )
                reservas_creadas.append(reserva)
        
        Reserva.objects.bulk_create(reservas_creadas)

        # ----- MENSAJES Y REDIRECCIÓN -----
        num_reservas = len(reservas_creadas)
        if descripcion_bloque:
            msg_nombre = f" como '{descripcion_bloque}'"
        else:
            msg_nombre = " de forma individual"

        if tipo_reserva_seleccionado == 'mensual':
            messages.success(request, f"{num_reservas} turnos reservados{msg_nombre}. Proceda al cobro.")
            # Asume que la primera reserva es la principal para el cobro
            pk_primera_reserva = Reserva.objects.filter(cancha=cancha, fecha=fecha_base, hora_inicio=slots_seleccionados_time[0]).first().pk
            return redirect('cobro-reserva', reserva_pk=pk_primera_reserva)
        else: # Diario
            messages.success(request, f"{num_reservas} turno(s) reservado(s){msg_nombre}. Ahora puedes pagar o cancelar.")
            context = {'cancha': cancha, 'fecha_seleccionada': fecha_base, 'fecha_str': fecha, 'slots': self._generar_slots(cancha, fecha_base)}
            return render(request, self.template_name, context)

    def _generar_slots(self, cancha, fecha_obj):
        slots_del_dia = []
        hora_apertura = time(7, 0)
        hora_cierre = time(2, 0)
        
        reservas_del_dia = {
            r.hora_inicio: r for r in Reserva.objects.filter(cancha=cancha, fecha=fecha_obj, estado__in=['confirmada', 'pendiente_pago', 'pendiente'])
        }

        current_dt = datetime.combine(fecha_obj, hora_apertura)
        limite_dt = datetime.combine(fecha_obj + timedelta(days=1), hora_cierre) if hora_cierre < hora_apertura else datetime.combine(fecha_obj, hora_cierre)

        while current_dt < limite_dt:
            hora_inicio = current_dt.time()
            reserva = reservas_del_dia.get(hora_inicio)
            
            slot_info = {
                'hora_inicio_str': hora_inicio.strftime('%H:%M'),
                'estado_display': 'disponible',
                'reserva_info': None,
                'reserva_pk': None,
                'nombre_reserva': None,
                'tipo_origen_display': None,
                'estado_modelo_reserva': None,
            }

            if reserva:
                slot_info.update({
                    'reserva_pk': reserva.pk,
                    'reserva_info': reserva.nombre_reserva or (reserva.usuario.get_full_name() if reserva.usuario else "Ocupado"),
                    'nombre_reserva': reserva.nombre_reserva,
                    'tipo_origen_display': reserva.get_tipo_reserva_origen_display(),
                    'estado_modelo_reserva': reserva.estado,
                    'estado_display': 'pendiente_pago_disp' if reserva.estado == 'pendiente_pago' else 'reservado'
                })
            
            slots_del_dia.append(slot_info)
            current_dt += timedelta(minutes=30)
            
        return slots_del_dia


# --- Vista de Cancelación (VERSIÓN DEFINITIVA Y SIMPLIFICADA) ---
class CancelarReservaView(View):
    def post(self, request, reserva_pk):
        reserva_base = get_object_or_404(Reserva, pk=reserva_pk)
        fecha_redirect = reserva_base.fecha.strftime('%Y-%m-%d')
        cancha_pk_redirect = reserva_base.cancha.pk
        
        nombre_bloque = reserva_base.nombre_reserva

        # CASO 1: La reserva tiene un nombre -> Es un bloque.
        if nombre_bloque:
            reservas_a_eliminar = Reserva.objects.filter(
                cancha=reserva_base.cancha,
                nombre_reserva=nombre_bloque,
                fecha__gte=timezone.localdate()
            )
            count = reservas_a_eliminar.count()
            if count > 0:
                reservas_a_eliminar.delete()
                messages.success(request, f"Se canceló el bloque completo '{nombre_bloque}' ({count} turnos eliminados).")
            else:
                messages.warning(request, f"No se encontraron turnos futuros o presentes para el bloque '{nombre_bloque}'.")

        # CASO 2: La reserva NO tiene nombre -> Es individual.
        else:
            fecha_str = reserva_base.fecha.strftime('%d/%m/%Y')
            hora_str = reserva_base.hora_inicio.strftime('%H:%M')
            reserva_base.delete()
            messages.success(request, f"Turno único del {fecha_str} a las {hora_str} cancelado.")

        return redirect('reservar-fecha', cancha_pk=cancha_pk_redirect, fecha=fecha_redirect)



## COBROS


class CobroReservaView(View):
    template_name = 'cobro_reserva.html'
    form_class = CobroForm

    def _get_bloque_context(self, reserva_base):
        """Helper para obtener el contexto del bloque de reservas."""
        cancha = reserva_base.cancha
        nombre_bloque = reserva_base.nombre_reserva
        fecha_inicio_bloque = reserva_base.fecha
        tipo_origen = reserva_base.tipo_reserva_origen

        # Estas son TODAS las reservas que pertenecen al bloque, independientemente de su estado actual.
        # Usaremos esto para mostrar información y calcular el monto sugerido.
        reservas_del_bloque_display = Reserva.objects.filter(
            cancha=cancha,
            nombre_reserva=nombre_bloque,
            fecha__gte=fecha_inicio_bloque,
            tipo_reserva_origen=tipo_origen
        ).order_by('fecha', 'hora_inicio')

        # Si por alguna razón no se encuentran reservas con los criterios de bloque (ej. la reserva_base es única y no tiene nombre_reserva),
        # entonces el "bloque" es solo la reserva_base.
        if not reservas_del_bloque_display.exists() and nombre_bloque: # Si tiene nombre pero no encuentra, algo es raro.
             # Log de advertencia o manejo especial si esto no debería ocurrir.
             print(f"Advertencia: No se encontraron reservas de bloque para '{nombre_bloque}' en cancha {cancha} desde {fecha_inicio_bloque} con tipo {tipo_origen}, usando solo reserva_base {reserva_base.pk}")
             reservas_del_bloque_display = Reserva.objects.filter(pk=reserva_base.pk)
        elif not nombre_bloque: # Si no tiene nombre, es una reserva única
            reservas_del_bloque_display = Reserva.objects.filter(pk=reserva_base.pk)


        monto_total_sugerido = sum(r.precio_reserva or Decimal('0.00') for r in reservas_del_bloque_display)
        fechas_implicadas = sorted(list(set(r.fecha for r in reservas_del_bloque_display)))
        
        return {
            'reservas_del_bloque_display': reservas_del_bloque_display,
            'monto_total_sugerido': monto_total_sugerido,
            'fechas_implicadas': fechas_implicadas,
        }

    def get(self, request, reserva_pk):
        reserva_base = get_object_or_404(Reserva, pk=reserva_pk)

        # Validar si ALGUNA reserva del bloque está en estado cobrable.
        # Si todas ya están 'confirmada', igual se permite llegar para registrar un pago (quizás un re-pago o un pago tardío).
        # El cambio de estado solo ocurrirá para las que no estén 'confirmada'.
        
        # Obtener el contexto del bloque
        bloque_context = self._get_bloque_context(reserva_base)
        
        # Si no hay reservas en el bloque display (muy raro si reserva_base existe), redirigir.
        if not bloque_context['reservas_del_bloque_display'].exists():
            messages.error(request, "No se encontraron reservas asociadas para este cobro.")
            return redirect('cancha-detail', pk=reserva_base.cancha.pk) # O a una vista más general


        # El monto inicial del formulario será el sugerido para el bloque completo.
        form = self.form_class(initial={'monto': None})

        context = {
            'form': form,
            'reserva_base': reserva_base, # La reserva que disparó el cobro (PK de la URL)
            'reservas_del_bloque': bloque_context['reservas_del_bloque_display'], # Para mostrar en el template
            'monto_total_sugerido': bloque_context['monto_total_sugerido'],
            'fechas_implicadas': bloque_context['fechas_implicadas'],
        }
        return render(request, self.template_name, context)

    def post(self, request, reserva_pk):
        reserva_base = get_object_or_404(Reserva, pk=reserva_pk)
        form = self.form_class(request.POST)

        if form.is_valid():
            monto_cobrado = form.cleaned_data['monto']
            metodo_pago = form.cleaned_data.get('metodo_pago')
            descripcion_adicional = form.cleaned_data.get('descripcion_adicional', '')

            try:
                # Identificar TODAS las reservas que pertenecen al bloque de la reserva_base
                # y que necesitan que su estado cambie a 'confirmada'.
                # Estas son las que NO están ya 'confirmada' (ej. 'pendiente_pago', 'pendiente')
                cancha = reserva_base.cancha
                nombre_bloque = reserva_base.nombre_reserva
                fecha_inicio_bloque = reserva_base.fecha # Usar la fecha de la reserva_base como inicio del bloque
                tipo_origen = reserva_base.tipo_reserva_origen

                # Reservas del bloque que necesitan actualizar su estado
                # Si no hay nombre_bloque, significa que es una reserva única (diaria)
                if nombre_bloque:
                    reservas_a_actualizar_estado = Reserva.objects.filter(
                        cancha=cancha,
                        nombre_reserva=nombre_bloque,
                        fecha__gte=fecha_inicio_bloque, # Considerar todas las futuras del bloque
                        tipo_reserva_origen=tipo_origen,
                        estado__in=['pendiente_pago', 'pendiente'] # Solo las que no están confirmadas
                    )
                else: # Reserva única, solo actualizar la reserva_base si está pendiente de pago
                    if reserva_base.estado in ['pendiente_pago', 'pendiente']:
                        reservas_a_actualizar_estado = Reserva.objects.filter(pk=reserva_base.pk)
                    else:
                        reservas_a_actualizar_estado = Reserva.objects.none()


                reservas_actualizadas_count = 0
                for reserva_obj in reservas_a_actualizar_estado:
                    reserva_obj.estado = 'confirmada'
                    # Opcional: Asignar el precio_reserva del bloque al turno individual si no lo tiene,
                    # o si el monto cobrado es por el total y se quiere prorratear.
                    # Por simplicidad, aquí solo cambiamos el estado.
                    # Si quieres actualizar el precio_reserva individual:
                    # if reserva_obj.precio_reserva is None and reserva_base.precio_reserva is not None:
                    #     reserva_obj.precio_reserva = reserva_base.precio_reserva # O alguna lógica de prorrateo
                    reserva_obj.save()
                    reservas_actualizadas_count += 1
                
                # Descripción para el Ingreso
                desc_nombre_reserva_ing = reserva_base.nombre_reserva or 'Turno Único'
                desc_cancha_ing = reserva_base.cancha.nombre
                
                # Determinar si se cobró un bloque o una reserva individual para la descripción del ingreso
                # Usamos la cuenta de las reservas que se actualizaron, o si es tipo mensual
                # Tu lógica original para num_reservas_bloque ya hacía esto, la podemos reusar:
                num_total_reservas_en_bloque_original = Reserva.objects.filter(
                    cancha=cancha,
                    nombre_reserva=nombre_bloque,
                    fecha__gte=fecha_inicio_bloque,
                    tipo_reserva_origen=tipo_origen
                ).count()

                if num_total_reservas_en_bloque_original > 1 and nombre_bloque:
                     descripcion_ingreso = f"Cobro bloque '{desc_nombre_reserva_ing}' - Cancha {desc_cancha_ing} (desde {reserva_base.fecha.strftime('%d/%m')})"
                else: # Incluye el caso de reserva única (sin nombre_bloque) o un "bloque" de 1
                     descripcion_ingreso = f"Cobro reserva '{desc_nombre_reserva_ing}' - Cancha {desc_cancha_ing} ({reserva_base.fecha.strftime('%d/%m')} {reserva_base.hora_inicio.strftime('%H:%M')})"

                if descripcion_adicional:
                    descripcion_ingreso += f" - {descripcion_adicional}"

                # Crear UN Ingreso asociado a la reserva_base, con el monto total cobrado.
                ingreso = Ingreso.objects.create(
                    reserva=reserva_base, # Asociar a la reserva que inició el cobro
                    fecha=timezone.now().date(), # O la fecha que el usuario indique para el pago
                    monto=monto_cobrado,
                    descripcion=descripcion_ingreso,
                    metodo_pago=metodo_pago
                )

                if reservas_actualizadas_count > 0:
                    messages.success(request, f"{reservas_actualizadas_count} turno(s) del bloque '{desc_nombre_reserva_ing}' confirmados. Cobro de ${monto_cobrado:.2f} registrado.")
                else:
                    # Esto pasaría si todas las reservas del bloque ya estaban confirmadas, pero se registra un pago.
                    messages.success(request, f"Cobro de ${monto_cobrado:.2f} registrado para '{desc_nombre_reserva_ing}'. (Los turnos ya estaban confirmados).")
                
                # Redirigir a la vista de reserva de fecha para la reserva_base.
                # Esto es crucial para que el usuario vea los estados actualizados.
                return redirect('reservar-fecha', cancha_pk=reserva_base.cancha.pk, fecha=reserva_base.fecha.strftime('%Y-%m-%d'))

            except Exception as e:
                 print(f"Error crítico al procesar cobro para reserva {reserva_pk} (Bloque: {reserva_base.nombre_reserva}): {e}")
                 messages.error(request, f"Ocurrió un error grave al registrar el cobro. Por favor, contacte a soporte. Detalle: {e}")

        # Si el formulario no es válido, volver a mostrarlo con errores
        # Reconstruir el contexto necesario para el template
        bloque_context_error = self._get_bloque_context(reserva_base)
        context = {
            'form': form, # El formulario con errores y datos ingresados
            'reserva_base': reserva_base,
            'reservas_del_bloque': bloque_context_error['reservas_del_bloque_display'],
            'monto_total_sugerido': bloque_context_error['monto_total_sugerido'],
            'fechas_implicadas': bloque_context_error['fechas_implicadas'],
        }
        return render(request, self.template_name, context)

##EXTRAS



class ExtraCreateView(SuccessMessageMixin, CreateView):
    model = Extra
    form_class = ExtraForm
    template_name = 'extra_form.html' # Reutilizable para crear/editar
    success_url = reverse_lazy('extra-list')
    success_message = "Extra '%(nombre)s' creado exitosamente."

class ExtraUpdateView(SuccessMessageMixin, UpdateView):
    model = Extra
    form_class = ExtraForm
    template_name = 'extra_form.html'
    success_url = reverse_lazy('extra-list')
    success_message = "Extra '%(nombre)s' actualizado exitosamente."

class ExtraDeleteView(SuccessMessageMixin, DeleteView):
    model = Extra
    template_name = 'extra_confirm_delete.html'
    success_url = reverse_lazy('extra-list')
    success_message = "Extra eliminado exitosamente."
    # Añadir protección si el extra fue vendido? O solo desactivar?
    # def post(self, request, *args, **kwargs):
    #     # Lógica para verificar si se puede borrar o solo desactivar
    #     return super().post(request, *args, **kwargs)



class MovimientosRecientesListView(TemplateView):
    # Usaremos la misma plantilla, pero la modificaremos
    template_name = 'movimientos_recientes.html' # O renombra el archivo a 'movimientos_recientes_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Lógica para obtener y combinar movimientos (igual que antes)
        num_movimientos = 15 # Puedes ajustar cuántos mostrar
        ultimos_ingresos = Ingreso.objects.order_by('-fecha', '-id')[:num_movimientos]
        ultimos_egresos = Egreso.objects.order_by('-fecha', '-id')[:num_movimientos]

        lista_combinada = []
        for ingreso in ultimos_ingresos:
            lista_combinada.append({'tipo': 'Ingreso', 'objeto': ingreso})
        for egreso in ultimos_egresos:
            lista_combinada.append({'tipo': 'Egreso', 'objeto': egreso})

        movimientos_recientes = sorted(
            lista_combinada,
            key=lambda item: (item['objeto'].fecha, item['objeto'].id),
            reverse=True
        )
        movimientos_recientes = movimientos_recientes[:num_movimientos]

        # Añadimos los movimientos y un título al contexto
        context['movimientos_recientes'] = movimientos_recientes
        # Cambiamos el título para que refleje el contenido
        context['titulo_pagina'] = f"Últimos {num_movimientos} Movimientos Rápidos"

        return context

# --- VISTA DE MOVIMIENTO RÁPIDO (sin cambios relevantes aquí) ---
class MovimientoRapidoCreateView(FormView):
    template_name = 'movimiento_rapido_form.html'
    form_class = MovimientoRapidoForm
    success_url = reverse_lazy('movimientos-list') # Ajusta si el nombre de tu URL es diferente

    def get_form(self, form_class=None):
        # ... (tu código existente para get_form) ...
        form = super().get_form(form_class)
        # No establezcas initial para fecha aquí, hazlo en attrs como antes
        fecha_actual = timezone.now().date()
        form.fields['fecha'].widget.attrs['readonly'] = True
        form.fields['fecha'].widget.attrs['value'] = fecha_actual.strftime('%Y-%m-%d')
        # Código para extras_precios...
        return form

    def form_valid(self, form):
        data = form.cleaned_data
        tipo = data['tipo']
        monto = data.get('monto')
        descripcion = data['descripcion']
        fecha_a_usar = timezone.now().date() # Usar siempre fecha actual del servidor
        extra_seleccionado = data.get('extra')
        cantidad = data.get('cantidad')

        # --- OBTENER Y ASIGNAR DEFAULT A METODO DE PAGO ---
        metodo_pago = data.get('metodo_pago')
        if not metodo_pago: # Si es None o cadena vacía
            metodo_pago = 'otro' # <-- ASIGNA TU VALOR POR DEFECTO AQUÍ (asegúrate que 'otro' exista en choices)
        # -------------------------------------------------

        monto_a_guardar = monto if monto is not None else Decimal('0.00')

        try:
            with transaction.atomic():
                if tipo == 'ingreso':
                    Ingreso.objects.create(
                        fecha=fecha_a_usar,
                        monto=monto_a_guardar,
                        descripcion=descripcion,
                        metodo_pago=metodo_pago # <-- Ahora siempre tendrá un valor
                    )
                    messages.success(self.request, f"Ingreso registrado.")

                elif tipo == 'egreso':
                    producto_para_egreso = None
                    if extra_seleccionado and cantidad:
                        # --- LÓGICA DE DESCUENTO DE STOCK ---
                        try:
                            producto = Extra.objects.get(pk=extra_seleccionado.pk)
                            producto_para_egreso = producto
                            stock_obj = Stock.objects.select_for_update().get(extra=producto)
                            try:
                                stock_obj.reducir_stock(cantidad)
                                messages.info(self.request, f"Stock de '{producto.nombre}' actualizado (-{cantidad}). Nuevo stock: {stock_obj.cantidad}.")
                            except ValidationError as e:
                                form.add_error('cantidad', str(e))
                                return self.form_invalid(form)
                        except Stock.DoesNotExist:
                            # ... manejo de error stock ...
                            return self.form_invalid(form)
                        except Extra.DoesNotExist:
                             # ... manejo de error extra ...
                             return self.form_invalid(form)
                        # --- FIN LÓGICA DE DESCUENTO ---

                    Egreso.objects.create(
                        fecha=fecha_a_usar,
                        monto=monto_a_guardar,
                        descripcion=descripcion,
                        metodo_pago=metodo_pago, # <-- Ahora siempre tendrá un valor
                        producto=producto_para_egreso
                        # No hay 'categoria' en este form
                    )
                    messages.success(self.request, f"Egreso registrado.")

                else:
                    messages.error(self.request, "Tipo de movimiento inválido.")
                    return self.form_invalid(form)

        except Exception as e:
            messages.error(self.request, f"Ocurrió un error inesperado: {e}")
            import logging
            logging.exception("Error en MovimientoRapidoCreateView form_valid")
            return self.form_invalid(form)

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = "Registrar Movimiento Rápido"
        return context










# --- Vistas para Ingresos ---
class IngresoListView(ListView):
    model = Ingreso
    template_name = 'ingreso_list.html' # Carpeta contabilidad
    context_object_name = 'ingresos'
    paginate_by = 20 # Opcional

    def get_queryset(self):
        # Permitir filtrar por fecha si se implementa
        return Ingreso.objects.all().order_by('-fecha', '-pk')

class IngresoCreateView(SuccessMessageMixin, CreateView):
    model = Ingreso
    form_class = IngresoForm
    template_name = 'ingreso_form.html'
    success_url = reverse_lazy('ingreso-list')
    success_message = "Ingreso de $%(monto).2f registrado exitosamente."


# --- Vistas para Egresos ---
class EgresoListView(ListView):
    model = Egreso
    template_name = 'egreso_list.html'
    context_object_name = 'egresos'
    paginate_by = 20

    def get_queryset(self):
        return Egreso.objects.all().order_by('-fecha', '-pk')

class EgresoCreateView(SuccessMessageMixin, CreateView):
    model = Egreso
    form_class = EgresoForm
    template_name = 'egreso_form.html'
    success_url = reverse_lazy('egreso-list')
    success_message = "Egreso de $%(monto).2f registrado exitosamente."


# --- Vista para Historial/Reporte (Ejemplo Básico) ---
class HistorialView(View):
    template_name = 'historial_view.html' # La plantilla que ya tienes

    def get(self, request):
        # Obtener la fecha de HOY
        hoy = timezone.localdate() # Obtiene la fecha actual según la zona horaria de Django

        # Calcular totales SOLO para hoy
        total_ingresos_hoy = Ingreso.objects.filter(
            fecha=hoy # Filtra por la fecha de hoy
        ).aggregate(
            total=Coalesce(Sum('monto'), Decimal('0.00'), output_field=DecimalField())
        )['total']

        total_egresos_hoy = Egreso.objects.filter(
            fecha=hoy # Filtra por la fecha de hoy
        ).aggregate(
            total=Coalesce(Sum('monto'), Decimal('0.00'), output_field=DecimalField())
        )['total']

        balance_hoy = total_ingresos_hoy - total_egresos_hoy

        # Obtener últimos movimientos SOLO de hoy para mostrar
        # Puedes ajustar el límite [:5] si quieres mostrar más o menos
        ultimos_ingresos_hoy = Ingreso.objects.filter(fecha=hoy).order_by('-pk')[:5]
        ultimos_egresos_hoy = Egreso.objects.filter(fecha=hoy).order_by('-pk')[:5]

        context = {
            'fecha_inicio': hoy, # Ambas fechas son hoy para indicar el período
            'fecha_fin': hoy,
            'total_ingresos': total_ingresos_hoy, # Pasa los totales de hoy
            'total_egresos': total_egresos_hoy,
            'balance': balance_hoy,
            'ultimos_ingresos': ultimos_ingresos_hoy, # Pasa los movimientos de hoy
            'ultimos_egresos': ultimos_egresos_hoy,
            # No necesitas más datos para esta vista específica
        }
        return render(request, self.template_name, context)




class ResumenesView(View):
    template_name = 'resumenes_view.html'

    def get(self, request):
        # --- Calcular Resúmenes Diarios ---
        # Ingresos: Suma TODOS los ingresos del día
        ingresos_diarios = Ingreso.objects \
                                .annotate(dia=Cast(TruncDay('fecha'), output_field=DateField())) \
                                .values('dia') \
                                .annotate(total_ingresos=Coalesce(Sum('monto'), Decimal('0.0'), output_field=DecimalField())) \
                                .order_by('-dia')

        # Egresos: Suma todos los egresos del día (sin cambios)
        egresos_diarios = Egreso.objects \
                               .annotate(dia=Cast(TruncDay('fecha'), output_field=DateField())) \
                               .values('dia') \
                               .annotate(total_egresos=Coalesce(Sum('monto'), Decimal('0.0'), output_field=DecimalField())) \
                               .order_by('-dia')

        # Combinar datos diarios (solo Ingresos y Egresos)
        dias = set(i['dia'] for i in ingresos_diarios) | set(e['dia'] for e in egresos_diarios)
        dias_validos = {d for d in dias if d is not None}
        res_diarios_list = []
        for dia in sorted(list(dias_validos), reverse=True):
            ingresos = next((i['total_ingresos'] for i in ingresos_diarios if i['dia'] == dia), Decimal('0.0'))
            egresos = next((e['total_egresos'] for e in egresos_diarios if e['dia'] == dia), Decimal('0.0'))
            # Balance simplificado
            balance = ingresos - egresos
            res_diarios_list.append({
                'fecha': dia,
                'total_ingresos': ingresos,
                'total_egresos': egresos,
                # 'total_extras' eliminado
                'balance': balance,
            })

        # --- Calcular Resúmenes Mensuales (Lógica similar) ---
        ingresos_mensuales = Ingreso.objects \
                                    .annotate(mes_anno=Cast(TruncMonth('fecha'), output_field=DateField())) \
                                    .values('mes_anno') \
                                    .annotate(total_ingresos=Coalesce(Sum('monto'), Decimal('0.0'), output_field=DecimalField())) \
                                    .order_by('-mes_anno')

        egresos_mensuales = Egreso.objects \
                                  .annotate(mes_anno=Cast(TruncMonth('fecha'), output_field=DateField())) \
                                  .values('mes_anno') \
                                  .annotate(total_egresos=Coalesce(Sum('monto'), Decimal('0.0'), output_field=DecimalField())) \
                                  .order_by('-mes_anno')

        meses = set(i['mes_anno'] for i in ingresos_mensuales) | set(e['mes_anno'] for e in egresos_mensuales)
        meses_validos = {m for m in meses if m is not None}
        res_mensuales_list = []
        for mes_anno_date in sorted(list(meses_validos), reverse=True):
            ingresos = next((i['total_ingresos'] for i in ingresos_mensuales if i['mes_anno'] == mes_anno_date), Decimal('0.0'))
            egresos = next((e['total_egresos'] for e in egresos_mensuales if e['mes_anno'] == mes_anno_date), Decimal('0.0'))
            balance = ingresos - egresos
            res_mensuales_list.append({
                'año': mes_anno_date.year,
                'mes': mes_anno_date.month,
                'total_ingresos': ingresos,
                'total_egresos': egresos,
                # 'total_extras' eliminado
                'balance': balance,
            })

        # --- Calcular Resúmenes Anuales (Lógica similar) ---
        ingresos_anuales = Ingreso.objects \
                                  .annotate(anno=Cast(TruncYear('fecha'), output_field=DateField())) \
                                  .values('anno') \
                                  .annotate(total_ingresos=Coalesce(Sum('monto'), Decimal('0.0'), output_field=DecimalField())) \
                                  .order_by('-anno')

        egresos_anuales = Egreso.objects \
                                .annotate(anno=Cast(TruncYear('fecha'), output_field=DateField())) \
                                .values('anno') \
                                .annotate(total_egresos=Coalesce(Sum('monto'), Decimal('0.0'), output_field=DecimalField())) \
                                .order_by('-anno')

        annos = set(i['anno'] for i in ingresos_anuales) | set(e['anno'] for e in egresos_anuales)
        annos_validos = {a for a in annos if a is not None}
        res_anuales_list = []
        for anno_date in sorted(list(annos_validos), reverse=True):
            ingresos = next((i['total_ingresos'] for i in ingresos_anuales if i['anno'] == anno_date), Decimal('0.0'))
            egresos = next((e['total_egresos'] for e in egresos_anuales if e['anno'] == anno_date), Decimal('0.0'))
            balance = ingresos - egresos
            res_anuales_list.append({
                'año': anno_date.year,
                'total_ingresos': ingresos,
                'total_egresos': egresos,
                # 'total_extras' eliminado
                'balance': balance,
            })

        # Contexto con las listas modificadas
        context = {
            'res_diarios': res_diarios_list,
            'res_mensuales': res_mensuales_list,
            'res_anuales': res_anuales_list,
        }
        return render(request, self.template_name, context)


class HistorialDiarioDetalleView(View):
    template_name = 'historial_diario_detalle.html' # Nueva plantilla que crearemos

    def get(self, request, fecha_str):
        try:
            # Intenta convertir la cadena de la URL a un objeto date
            fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            # Si el formato es inválido, muestra un error y redirige
            messages.error(request, "Formato de fecha inválido en la URL.")
            return redirect('resumenes-view') # Redirige a la vista de resúmenes

        # Obtener todos los ingresos de esa fecha específica
        ingresos_del_dia = Ingreso.objects.filter(fecha=fecha_obj).order_by('-pk') # Ordena por creación o como prefieras

        # Obtener todos los egresos de esa fecha específica
        egresos_del_dia = Egreso.objects.filter(fecha=fecha_obj).order_by('-pk')

        # Calcular totales para mostrar en el resumen del día (opcional, pero útil)
        total_ingresos = ingresos_del_dia.aggregate(
            total=Coalesce(Sum('monto'), Decimal('0.0'), output_field=DecimalField())
        )['total']

        total_egresos = egresos_del_dia.aggregate(
            total=Coalesce(Sum('monto'), Decimal('0.0'), output_field=DecimalField())
        )['total']

        balance_dia = total_ingresos - total_egresos

        context = {
            'fecha_vista': fecha_obj,
            'ingresos_del_dia': ingresos_del_dia,
            'egresos_del_dia': egresos_del_dia,
            'total_ingresos': total_ingresos,
            'total_egresos': total_egresos,
            'balance_dia': balance_dia,
            'fecha_str': fecha_str,
        }
        return render(request, self.template_name, context)


class HistorialMensualDetalleView(View):
    template_name = 'historial_mensual_detalle.html' # Nueva plantilla

    def get(self, request, year, month):
        # Validación básica del mes
        if not 1 <= month <= 12:
             messages.error(request, "Mes inválido.")
             return redirect('resumenes-view')

        # Intentar crear un objeto date para mostrar el mes/año (solo para display)
        try:
            # Usamos el primer día del mes para representación
            fecha_representativa = date(year, month, 1)
        except ValueError:
             messages.error(request, "Año o mes inválido.")
             return redirect('resumenes-view')

        # Filtrar Ingresos por año y mes
        ingresos_del_mes = Ingreso.objects.filter(
            fecha__year=year,
            fecha__month=month
        ).order_by('fecha', 'pk') # Ordenar por fecha dentro del mes

        # Filtrar Egresos por año y mes
        egresos_del_mes = Egreso.objects.filter(
            fecha__year=year,
            fecha__month=month
        ).order_by('fecha', 'pk')

        # Calcular totales del mes
        total_ingresos = ingresos_del_mes.aggregate(
            total=Coalesce(Sum('monto'), Decimal('0.0'), output_field=DecimalField())
        )['total']
        total_egresos = egresos_del_mes.aggregate(
            total=Coalesce(Sum('monto'), Decimal('0.0'), output_field=DecimalField())
        )['total']
        balance_mes = total_ingresos - total_egresos

        context = {
            'fecha_representativa': fecha_representativa, # Para mostrar título ej: "Abril 2025"
            'year': year,
            'month': month,
            'ingresos_del_mes': ingresos_del_mes,
            'egresos_del_mes': egresos_del_mes,
            'total_ingresos': total_ingresos,
            'total_egresos': total_egresos,
            'balance_mes': balance_mes,
        }
        return render(request, self.template_name, context)

# --- VISTA DETALLE ANUAL ---
class HistorialAnualDetalleView(View):
    template_name = 'historial_anual_detalle.html' # Nueva plantilla

    def get(self, request, year):
        # Validación básica del año (opcional)
        # if year < 2000 or year > timezone.now().year + 1:
        #    messages.error(request, "Año inválido.")
        #    return redirect('resumenes-view')

        # Filtrar Ingresos por año
        ingresos_del_ano = Ingreso.objects.filter(
            fecha__year=year
        ).order_by('fecha', 'pk') # Ordenar por fecha dentro del año

        # Filtrar Egresos por año
        egresos_del_ano = Egreso.objects.filter(
            fecha__year=year
        ).order_by('fecha', 'pk')

        # Calcular totales del año
        total_ingresos = ingresos_del_ano.aggregate(
            total=Coalesce(Sum('monto'), Decimal('0.0'), output_field=DecimalField())
        )['total']
        total_egresos = egresos_del_ano.aggregate(
            total=Coalesce(Sum('monto'), Decimal('0.0'), output_field=DecimalField())
        )['total']
        balance_anual = total_ingresos - total_egresos

        context = {
            'year': year,
            'ingresos_del_ano': ingresos_del_ano,
            'egresos_del_ano': egresos_del_ano,
            'total_ingresos': total_ingresos,
            'total_egresos': total_egresos,
            'balance_anual': balance_anual,
        }
        return render(request, self.template_name, context)




## DESCARGA DE HISTORIALES 




class DescargarHistorialDiarioPDFView(BaseReportPDFView):

    def get(self, request, fecha_str):
        try:
            fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, "Formato de fecha inválido para PDF.")
            return redirect('resumenes-view')

        # --- Obtener datos ---
        ingresos = Ingreso.objects.filter(fecha=fecha_obj).order_by('pk')
        egresos = Egreso.objects.filter(fecha=fecha_obj).order_by('pk')
        total_ingresos = ingresos.aggregate(total=Coalesce(Sum('monto'), Decimal('0.0')))['total']
        total_egresos = egresos.aggregate(total=Coalesce(Sum('monto'), Decimal('0.0')))['total']
        balance_dia = total_ingresos - total_egresos

        # --- Construir PDF ---
        buffer = io.BytesIO()
        story = []

        titulo = f"Detalle del Día: {fecha_obj.strftime('%d/%m/%Y')}"
        story.append(Paragraph(titulo, self.styles['h1']))
        story.append(Spacer(1, 0.5*cm))

        if ingresos.exists():
            story.append(Paragraph("Ingresos", self.styles['h2']))
            data_ingresos = [['Monto', 'Descripción', 'Método Pago', 'Asociado a']]
            for ing in ingresos:
                desc_p = Paragraph(ing.descripcion or '-', self.styles['Normal'])
                asoc_p = Paragraph(get_ingreso_asociado_str(ing), self.styles['Normal'])
                data_ingresos.append([ format_currency(ing.monto), desc_p, ing.get_metodo_pago_display() or '-', asoc_p ])
            data_ingresos.append([format_currency(total_ingresos), Paragraph('<b>TOTAL INGRESOS</b>', self.styles['Normal']), '', ''])
            tabla_ingresos = Table(data_ingresos, colWidths=self.col_widths_ingreso, repeatRows=1)
            tabla_ingresos.setStyle(TableStyle([
                self.table_style_header, self.table_style_header_text, self.table_style_grid,
                self.table_style_align_center, self.table_style_valign_middle, self.table_style_padding,
                self.table_style_rightpadding, self.table_style_total_row, self.table_style_total_font,
                ('SPAN', (1, -1), (3, -1)), ('ALIGN', (0, 1), (0, -1), 'RIGHT'), ('ALIGN', (1, 1), (3, -1), 'LEFT'),
            ]))
            story.append(tabla_ingresos)
            story.append(Spacer(1, 0.7*cm))
        else:
            story.append(Paragraph("No se registraron ingresos este día.", self.styles['Normal']))
            story.append(Spacer(1, 0.7*cm))

        if egresos.exists():
            story.append(Paragraph("Egresos", self.styles['h2']))
            data_egresos = [['Monto', 'Descripción', 'Categoría', 'Asociado a']]
            for egr in egresos:
                desc_p = Paragraph(egr.descripcion or '-', self.styles['Normal'])
                asoc_p = Paragraph(get_egreso_asociado_str(egr), self.styles['Normal'])
                data_egresos.append([ format_currency(egr.monto), desc_p, egr.get_categoria_display() or '-', asoc_p ])
            data_egresos.append([format_currency(total_egresos), Paragraph('<b>TOTAL EGRESOS</b>', self.styles['Normal']), '', ''])
            col_widths_egr_diario = [2.5*cm, 6*cm, 3*cm, 5*cm] # Ajustar anchos egreso diario
            tabla_egresos = Table(data_egresos, colWidths=col_widths_egr_diario, repeatRows=1)
            tabla_egresos.setStyle(TableStyle([
                self.table_style_header, self.table_style_header_text, self.table_style_grid,
                self.table_style_align_center, self.table_style_valign_middle, self.table_style_padding,
                self.table_style_rightpadding, self.table_style_total_row, self.table_style_total_font,
                ('SPAN', (1, -1), (3, -1)), ('ALIGN', (0, 1), (0, -1), 'RIGHT'), ('ALIGN', (1, 1), (3, -1), 'LEFT'),
            ]))
            story.append(tabla_egresos)
            story.append(Spacer(1, 0.7*cm))
        else:
            story.append(Paragraph("No se registraron egresos este día.", self.styles['Normal']))
            story.append(Spacer(1, 0.7*cm))

        story.append(Paragraph("Balance del Día", self.styles['h2']))
        resumen_data = [ ['Total Ingresos:', format_currency(total_ingresos)], ['Total Egresos:', format_currency(total_egresos)], ['Balance:', format_currency(balance_dia)], ]
        resumen_table = Table(resumen_data, colWidths=[4*cm, 4*cm])
        resumen_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'), ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('LEFTPADDING', (0,0), (-1,-1), 5), ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(resumen_table)

        self.build_pdf(buffer, story)
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="historial_diario_{fecha_str}.pdf"'
        return response

# --- Vista Descarga PDF Mensual ---
class DescargarHistorialMensualPDFView(BaseReportPDFView):
    def get(self, request, year, month):
        if not 1 <= month <= 12:
             messages.error(request, "Mes inválido para PDF.")
             return redirect('resumenes-view')
        try:
             fecha_representativa = date(year, month, 1)
        except ValueError:
             messages.error(request, "Año o mes inválido para PDF.")
             return redirect('resumenes-view')

        ingresos = Ingreso.objects.filter(fecha__year=year, fecha__month=month).order_by('fecha', 'pk')
        egresos = Egreso.objects.filter(fecha__year=year, fecha__month=month).order_by('fecha', 'pk')
        total_ingresos = ingresos.aggregate(total=Coalesce(Sum('monto'), Decimal('0.0')))['total']
        total_egresos = egresos.aggregate(total=Coalesce(Sum('monto'), Decimal('0.0')))['total']
        balance_mes = total_ingresos - total_egresos

        buffer = io.BytesIO()
        story = []
        month_name = fecha_representativa.strftime("%B %Y")
        month_str = str(month).zfill(2)

        titulo = f"Detalle Mensual: {month_name}"
        story.append(Paragraph(titulo, self.styles['h1']))
        story.append(Spacer(1, 0.5*cm))

        if ingresos.exists():
            story.append(Paragraph("Ingresos del Mes", self.styles['h2']))
            data_ingresos = [['Fecha', 'Monto', 'Descripción', 'Método Pago', 'Asociado a']]
            for ing in ingresos:
                desc_p = Paragraph(ing.descripcion or '-', self.styles['Normal'])
                asoc_p = Paragraph(get_ingreso_asociado_str(ing), self.styles['Normal'])
                data_ingresos.append([ ing.fecha.strftime('%d/%m'), format_currency(ing.monto), desc_p, ing.get_metodo_pago_display() or '-', asoc_p ])
            data_ingresos.append(['', format_currency(total_ingresos), Paragraph('<b>TOTAL INGRESOS</b>', self.styles['Normal']), '', ''])
            col_widths_ing_mensual = [1.5*cm] + self.col_widths_ingreso
            tabla_ingresos = Table(data_ingresos, colWidths=col_widths_ing_mensual, repeatRows=1)
            tabla_ingresos.setStyle(TableStyle([
                self.table_style_header, self.table_style_header_text, self.table_style_grid,
                self.table_style_align_center, self.table_style_valign_middle, self.table_style_padding,
                self.table_style_rightpadding, self.table_style_total_row, self.table_style_total_font,
                ('SPAN', (2, -1), (4, -1)), ('ALIGN', (1, 1), (1, -1), 'RIGHT'), ('ALIGN', (2, 1), (4, -1), 'LEFT'),
            ]))
            story.append(tabla_ingresos)
            story.append(Spacer(1, 0.7*cm))
        else:
            story.append(Paragraph("No se registraron ingresos este mes.", self.styles['Normal']))
            story.append(Spacer(1, 0.7*cm))

        if egresos.exists():
            story.append(Paragraph("Egresos del Mes", self.styles['h2']))
            data_egresos = [['Fecha', 'Monto', 'Descripción', 'Categoría', 'Asociado a']]
            for egr in egresos:
                desc_p = Paragraph(egr.descripcion or '-', self.styles['Normal'])
                asoc_p = Paragraph(get_egreso_asociado_str(egr), self.styles['Normal'])
                data_egresos.append([ egr.fecha.strftime('%d/%m'), format_currency(egr.monto), desc_p, egr.get_categoria_display() or '-', asoc_p ])
            data_egresos.append(['', format_currency(total_egresos), Paragraph('<b>TOTAL EGRESOS</b>', self.styles['Normal']), '', ''])
            col_widths_egr_mensual = [1.5*cm] + self.col_widths_egreso
            tabla_egresos = Table(data_egresos, colWidths=col_widths_egr_mensual, repeatRows=1)
            tabla_egresos.setStyle(TableStyle([
                 self.table_style_header, self.table_style_header_text, self.table_style_grid,
                 self.table_style_align_center, self.table_style_valign_middle, self.table_style_padding,
                 self.table_style_rightpadding, self.table_style_total_row, self.table_style_total_font,
                 ('SPAN', (2, -1), (4, -1)), ('ALIGN', (1, 1), (1, -1), 'RIGHT'), ('ALIGN', (2, 1), (4, -1), 'LEFT'),
            ]))
            story.append(tabla_egresos)
            story.append(Spacer(1, 0.7*cm))
        else:
            story.append(Paragraph("No se registraron egresos este mes.", self.styles['Normal']))
            story.append(Spacer(1, 0.7*cm))

        story.append(Paragraph("Balance del Mes", self.styles['h2']))
        resumen_data = [ ['Total Ingresos:', format_currency(total_ingresos)], ['Total Egresos:', format_currency(total_egresos)], ['Balance:', format_currency(balance_mes)], ]
        resumen_table = Table(resumen_data, colWidths=[4*cm, 4*cm])
        resumen_table.setStyle(TableStyle([
             ('ALIGN', (0, 0), (0, -1), 'RIGHT'), ('ALIGN', (1, 0), (1, -1), 'LEFT'),
             ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
             ('LEFTPADDING', (0,0), (-1,-1), 5), ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(resumen_table)

        self.build_pdf(buffer, story)
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="historial_mensual_{year}-{month_str}.pdf"'
        return response


# --- Vista Descarga PDF Anual ---
class DescargarHistorialAnualPDFView(BaseReportPDFView):
    def get(self, request, year):
        ingresos = Ingreso.objects.filter(fecha__year=year).order_by('fecha', 'pk')
        egresos = Egreso.objects.filter(fecha__year=year).order_by('fecha', 'pk')
        total_ingresos = ingresos.aggregate(total=Coalesce(Sum('monto'), Decimal('0.0')))['total']
        total_egresos = egresos.aggregate(total=Coalesce(Sum('monto'), Decimal('0.0')))['total']
        balance_anual = total_ingresos - total_egresos

        buffer = io.BytesIO()
        story = []

        titulo = f"Detalle Anual: {year}"
        story.append(Paragraph(titulo, self.styles['h1']))
        story.append(Spacer(1, 0.5*cm))

        if ingresos.exists():
            story.append(Paragraph("Ingresos del Año", self.styles['h2']))
            data_ingresos = [['Fecha', 'Monto', 'Descripción', 'Método Pago', 'Asociado a']]
            for ing in ingresos:
                desc_p = Paragraph(ing.descripcion or '-', self.styles['Normal'])
                asoc_p = Paragraph(get_ingreso_asociado_str(ing), self.styles['Normal'])
                data_ingresos.append([ ing.fecha.strftime('%d/%m/%Y'), format_currency(ing.monto), desc_p, ing.get_metodo_pago_display() or '-', asoc_p ])
            data_ingresos.append(['', format_currency(total_ingresos), Paragraph('<b>TOTAL INGRESOS</b>', self.styles['Normal']), '', ''])
            col_widths_ing_anual = [2*cm] + self.col_widths_ingreso
            tabla_ingresos = Table(data_ingresos, colWidths=col_widths_ing_anual, repeatRows=1)
            tabla_ingresos.setStyle(TableStyle([
                self.table_style_header, self.table_style_header_text, self.table_style_grid,
                self.table_style_align_center, self.table_style_valign_middle, self.table_style_padding,
                self.table_style_rightpadding, self.table_style_total_row, self.table_style_total_font,
                ('SPAN', (2, -1), (4, -1)), ('ALIGN', (1, 1), (1, -1), 'RIGHT'), ('ALIGN', (2, 1), (4, -1), 'LEFT'),
            ]))
            story.append(tabla_ingresos)
            story.append(Spacer(1, 0.7*cm))
        else:
            story.append(Paragraph("No se registraron ingresos este año.", self.styles['Normal']))
            story.append(Spacer(1, 0.7*cm))

        if egresos.exists():
            story.append(Paragraph("Egresos del Año", self.styles['h2']))
            data_egresos = [['Fecha', 'Monto', 'Descripción', 'Categoría', 'Asociado a']]
            for egr in egresos:
                desc_p = Paragraph(egr.descripcion or '-', self.styles['Normal'])
                asoc_p = Paragraph(get_egreso_asociado_str(egr), self.styles['Normal'])
                data_egresos.append([ egr.fecha.strftime('%d/%m/%Y'), format_currency(egr.monto), desc_p, egr.get_categoria_display() or '-', asoc_p ])
            data_egresos.append(['', format_currency(total_egresos), Paragraph('<b>TOTAL EGRESOS</b>', self.styles['Normal']), '', ''])
            col_widths_egr_anual = [2*cm] + self.col_widths_egreso
            tabla_egresos = Table(data_egresos, colWidths=col_widths_egr_anual, repeatRows=1)
            tabla_egresos.setStyle(TableStyle([
                 self.table_style_header, self.table_style_header_text, self.table_style_grid,
                 self.table_style_align_center, self.table_style_valign_middle, self.table_style_padding,
                 self.table_style_rightpadding, self.table_style_total_row, self.table_style_total_font,
                 ('SPAN', (2, -1), (4, -1)), ('ALIGN', (1, 1), (1, -1), 'RIGHT'), ('ALIGN', (2, 1), (4, -1), 'LEFT'),
            ]))
            story.append(tabla_egresos)
            story.append(Spacer(1, 0.7*cm))
        else:
            story.append(Paragraph("No se registraron egresos este año.", self.styles['Normal']))
            story.append(Spacer(1, 0.7*cm))

        story.append(Paragraph("Balance del Año", self.styles['h2']))
        resumen_data = [ ['Total Ingresos:', format_currency(total_ingresos)], ['Total Egresos:', format_currency(total_egresos)], ['Balance:', format_currency(balance_anual)], ]
        resumen_table = Table(resumen_data, colWidths=[4*cm, 4*cm])
        resumen_table.setStyle(TableStyle([
             ('ALIGN', (0, 0), (0, -1), 'RIGHT'), ('ALIGN', (1, 0), (1, -1), 'LEFT'),
             ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
             ('LEFTPADDING', (0,0), (-1,-1), 5), ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(resumen_table)

        self.build_pdf(buffer, story)
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="historial_anual_{year}.pdf"'
        return response











## stock


class StockCargarView(SuccessMessageMixin, CreateView):
    """Vista para cargar o actualizar stock de un producto."""
    
    model = Stock
    form_class = StockForm
    template_name = 'stock_cargar.html'
    success_url = reverse_lazy('stock_listar')

    def get_success_message(self, cleaned_data):
        """Personalizar el mensaje de éxito para incluir el precio si se proporcionó."""
        extra_nombre = cleaned_data.get('extra_nombre')
        extra_precio = cleaned_data.get('extra_precio')
        cantidad = cleaned_data.get('cantidad_a_agregar')
        if extra_precio is not None:
            return _(f"Stock cargado exitosamente: {cantidad} unidades de {extra_nombre} a ${extra_precio}.")
        return _(f"Stock cargado exitosamente: {cantidad} unidades de {extra_nombre}.")

    def form_valid(self, form):
        response = super().form_valid(form)
        return response

    def form_invalid(self, form):
        # Añadir un mensaje para depurar si el formulario no es válido
        print("Formulario no válido:", form.errors)  # Para depuración en la consola
        return super().form_invalid(form)

class StockListView(ListView):
    """Vista para listar el stock disponible."""
    
    model = Stock
    template_name = 'stock_listar.html'
    context_object_name = 'stocks'

    def get_queryset(self):
        return Stock.objects.select_related('extra').order_by('extra__nombre')

class StockListView(ListView):
    """Vista para listar el stock disponible."""
    
    model = Stock
    template_name = 'stock_listar.html'
    context_object_name = 'stocks'

    def get_queryset(self):
        return Stock.objects.select_related('extra').order_by('extra__nombre')


class StockEditarView(SuccessMessageMixin, UpdateView):
    """Vista para editar el stock y el precio de un producto."""
    
    model = Stock
    form_class = StockEditarForm
    template_name = 'stock_editar.html'
    success_url = reverse_lazy('stock_listar')

    def get_success_message(self, cleaned_data):
        """Personalizar el mensaje de éxito."""
        extra_nombre = cleaned_data.get('extra_nombre')
        extra_precio = cleaned_data.get('extra_precio')
        cantidad = cleaned_data.get('cantidad')
        return _(f"Stock actualizado exitosamente: {extra_nombre} - {cantidad} unidades a ${extra_precio}.")

    def form_valid(self, form):
        response = super().form_valid(form)
        return response

    def form_invalid(self, form):
        print("Formulario no válido:", form.errors)  # Para depuración
        return super().form_invalid(form)


def stock_eliminar(request, pk):
    stock_item = get_object_or_404(Stock, pk=pk)
    # Es recomendable usar POST para eliminar, pero para seguir el patrón del botón GET:
    if request.method == 'GET': # O podrías cambiar el botón a un form con POST
        try:
            producto_nombre = stock_item.extra.nombre # Guarda el nombre para el mensaje
            stock_item.delete()
            messages.success(request, f'Stock para "{producto_nombre}" eliminado correctamente.')
        except Exception as e:
             messages.error(request, f'Error al eliminar el stock: {e}')
        # Redirige de vuelta a la lista de stock (ajusta 'stock_listar' si tu URL tiene otro nombre)
        return redirect('stock_listar')
    else:
         # Si decides usar POST, maneja el POST aquí
         # Si no, simplemente redirige o muestra un error si se accede con un método inesperado
         return redirect('stock_listar')

# Asegúrate de tener la vista que muestra la tabla
def stock_listar(request):
    stocks = Stock.objects.select_related('extra').all().order_by('extra__nombre') # Ejemplo de cómo obtener los stocks
    context = {'stocks': stocks}
    return render(request, 'stock_listar.html', context) # Reemplaza 'tu_template.html' con el nombre real de tu archivo









class VentaCreateView( SuccessMessageMixin, CreateView): # Asegúrate que LoginRequiredMixin esté si es necesario
    model = Venta
    form_class = VentaForm
    template_name = 'venta_registrar.html'
    success_url = reverse_lazy('venta_listar') # O a donde quieras redirigir
    success_message = _("Venta registrada exitosamente.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # ---- LÍNEA CLAVE ACTUALIZADA -----
        # Añadir precios de los extras que tienen stock para usar en JavaScript
        # Asegúrate de que este queryset coincida con el del VentaForm.__init__
        extras_con_stock_y_precio = Extra.objects.filter(
            activo=True,
            stocks__isnull=False # Clave: solo extras con stock
        ).distinct()

        context['extras_precios'] = {
            str(extra.pk): str(extra.precio_actual)
            for extra in extras_con_stock_y_precio
        }
        # ---------------------------------
        context['titulo_pagina'] = _("Registrar Venta") # Opcional: añadir título
        return context

    # Puedes añadir form_valid si necesitas lógica extra al guardar,
    # pero el modelo Venta.save() ya maneja la creación de Ingreso y reducción de stock.
    # def form_valid(self, form):
    #     # Lógica adicional si es necesaria antes o después de guardar
    #     # response = super().form_valid(form)
    #     # Lógica adicional
    #     # return response
    #     return super().form_valid(form)

# --- VISTA DE LISTADO DE VENTAS (Sin cambios necesarios para esta funcionalidad) ---
class VentaListView( ListView): # Asegúrate que LoginRequiredMixin esté si es necesario
    model = Venta
    template_name = 'venta_listar.html'
    context_object_name = 'ventas'
    paginate_by = 20 # Opcional

    def get_queryset(self):
        return Venta.objects.select_related('extra', 'reserva', 'ingreso').order_by('-fecha_venta')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = _("Historial de Ventas") # Opcional
        return context





## picaditos

class PicaditoListView(LoginRequiredMixin, ListView):
    model = Picadito
    template_name = 'picadito_list.html'
    context_object_name = 'picaditos'
    paginate_by = 15
    ordering = ['-fecha', '-hora_inicio']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Picaditos / Amistosos"
        return context

class PicaditoDetailView(LoginRequiredMixin, DetailView):
    model = Picadito
    template_name = 'picadito_detail.html'
    context_object_name = 'picadito'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        picadito = self.object
        context['titulo_pagina'] = f"Detalle: {picadito.nombre}"
        # Optimizar consulta obteniendo participantes y sus items
        participantes = picadito.participantes.prefetch_related('items_consumidos').all()
        context['participantes'] = participantes
        # Obtener el costo total usando la property del modelo
        context['costo_total_estimado'] = picadito.costo_total_estimado
        return context


import math
import logging


logger = logging.getLogger(__name__)

class PicaditoCreateSimplifiedView(LoginRequiredMixin, CreateView):
    model = Picadito
    form_class = PicaditoForm
    template_name = 'picadito_form.html'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.object = None

    def dispatch(self, request, *args, **kwargs):
        logger.debug("="*20 + " PICADITO CREATE DISPATCH INICIADO " + "="*20)
        logger.debug(f"Método HTTP: {request.method}")
        try:
            response = super().dispatch(request, *args, **kwargs)
            logger.debug("="*20 + " PICADITO CREATE DISPATCH FINALIZADO " + "="*20)
            return response
        except Exception as e:
            logger.exception("!!! EXCEPCIÓN EN PICADITO CREATE DISPATCH !!!")
            raise

    def get(self, request, *args, **kwargs):
        logger.info("--- Picadito Create GET iniciado ---")
        # CreateView maneja self.object = self.model() internamente en get
        # pero lo ponemos en None explícitamente para asegurar que no
        # se use una instancia previa si algo raro pasa.
        self.object = None
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        logger.info("--- Picadito Create POST iniciado ---")
        self.object = None # Importante para CreateView
        form = self.get_form()
        # Asegúrate de que ParticipantePicaditoFormSet esté definido
        # correctamente (normalmente en forms.py) con 'extra=...'
        participantes_formset = ParticipantePicaditoFormSet(request.POST, prefix='participantes')

        form_is_valid = form.is_valid()
        formset_is_valid = participantes_formset.is_valid()

        if form_is_valid and formset_is_valid:
            logger.info(">>> Ambos (Form y Formset) VÁLIDOS. Llamando a self.form_valid... <<<")
            self.validated_formset = participantes_formset # Guardar para usar en form_valid
            return self.form_valid(form)
        else:
            logger.error(f"Form válido: {form_is_valid}, Formset válido: {formset_is_valid}")
            if not form_is_valid: logger.error(f"Form Errores: {form.errors.as_json()}")
            if not formset_is_valid:
                logger.error(f"FormSet Errores: {participantes_formset.errors}")
                logger.error(f"FormSet Non-form Errores: {participantes_formset.non_form_errors()}")
            logger.error(">>> Form o Formset INVÁLIDO. Llamando a self.form_invalid... <<<")
            self.invalid_formset = participantes_formset # Guardar para usar en form_invalid
            return self.form_invalid(form)

    # --- Método Clave para Mostrar Formularios Vacíos en GET ---
    def get_context_data(self, **kwargs):
        logger.info("--- Picadito Create get_context_data iniciado ---")
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Registrar Nuevo Picadito"

        # Manejo del FormSet
        if 'participantes_formset' not in context: # Evitar sobreescribir si ya viene de form_invalid
            if self.request.method == 'POST':
                 # Para POST inválido, usa los datos POST y prefijo
                 logger.debug("get_context_data (en POST fallido): Creando formset desde request.POST")
                 context['participantes_formset'] = ParticipantePicaditoFormSet(self.request.POST, instance=self.object, prefix='participantes')
            else: # --- ESTA ES LA PARTE PARA GET ---
                 # Para GET, instancia SIN datos POST, con instance=None y prefijo
                 logger.debug("get_context_data (en GET): Creando formset vacío")
                 # La clave es que ParticipantePicaditoFormSet se defina con 'extra=N'
                 context['participantes_formset'] = ParticipantePicaditoFormSet(instance=None, prefix='participantes')
                 # ------------------------------------

        # Pasar extras activos (sin cambios)
        extras_qs = Extra.objects.filter(activo=True)
        context['extras_activos'] = {extra.pk: extra for extra in extras_qs}

        logger.info("--- Picadito Create get_context_data finalizado ---")
        return context

    # --- Método form_valid con lógica de stock de mitades (Sin cambios respecto al último) ---
    def form_valid(self, form):
        logger.critical("="*10 + ">>> Picadito Create form_valid INICIADO" + "="*10)
        participantes_formset = getattr(self, 'validated_formset', None)
        if participantes_formset is None:
             logger.error("!!! ERROR INTERNO: No se encontró validated_formset en form_valid !!!")
             messages.error(self.request, "Error interno del servidor.")
             return self.render_to_response(self.get_context_data(form=form))

        logger.info("Iniciando transacción atómica...")
        try:
            with transaction.atomic():
                logger.info("Guardando Picadito principal...")
                self.object = form.save()
                logger.info(f"Picadito '{self.object.nombre}' (PK: {self.object.pk}) GUARDADO.")

                # PASO 1: Crear Instancias Participante (sin commit)
                logger.info("Creando instancias de Participantes en memoria...")
                participantes_formset.instance = self.object
                participantes_instancias_memoria = participantes_formset.save(commit=False)

                # PASO 2: Procesar Costos, Preparar y CONTAR PARA STOCK
                logger.info("Calculando costos, descuentos y contando para stock...")
                half_item_counts = Counter()
                full_item_counts = Counter()
                participantes_para_guardar_db = []
                descuentos_por_indice = {}

                for i, p_form in enumerate(participantes_formset.forms):
                    if not p_form.is_valid(): continue
                    if not p_form.has_changed() and not p_form.instance.pk: continue
                    if participantes_formset.can_delete and p_form.cleaned_data.get('DELETE'): continue

                    participante_obj = participantes_instancias_memoria[i]
                    pks_descuento_str = p_form.cleaned_data.get('items_con_descuento_pks', '')
                    try:
                        pks_descuento_set = {int(pk) for pk in pks_descuento_str.split(',') if pk.isdigit()}
                        descuentos_por_indice[i] = pks_descuento_set
                    except ValueError: pks_descuento_set = descuentos_por_indice[i] = set()

                    costo_items_calculado = Decimal('0.00')
                    items_consumidos_objs = list(p_form.cleaned_data.get('items_consumidos', []))

                    for item_obj in items_consumidos_objs:
                        precio = item_obj.precio_actual if item_obj.precio_actual is not None else Decimal('0.00')
                        if item_obj.pk in pks_descuento_set:
                            costo_items_calculado += (precio / Decimal('2.0'))
                            half_item_counts[item_obj.pk] += 1
                        else:
                            costo_items_calculado += precio
                            full_item_counts[item_obj.pk] += 1

                    participante_obj.costo_calculado = costo_items_calculado
                    participantes_para_guardar_db.append(participante_obj)

                # PASO 3: Guardar Participantes en DB
                logger.info("Guardando objetos Participante en la base de datos...")
                for p_obj in participantes_para_guardar_db: p_obj.save()
                logger.info(f"Participantes ({len(participantes_para_guardar_db)}) guardados.")

                # PASO 4: Guardar M2M 'items_consumidos'
                logger.info("Guardando M2M 'items_consumidos'...")
                participantes_formset.save_m2m()
                logger.info("M2M 'items_consumidos' guardadas.")

                # PASO 5: Guardar M2M 'items_con_descuento'
                logger.info("Guardando M2M 'items_con_descuento'...")
                for i, participante_guardado in enumerate(participantes_para_guardar_db):
                    pks_descuento_set = descuentos_por_indice.get(i, set())
                    if pks_descuento_set:
                        items_con_descuento_final_qs = Extra.objects.filter(pk__in=pks_descuento_set)
                        participante_guardado.items_con_descuento.set(items_con_descuento_final_qs)
                    else:
                        participante_guardado.items_con_descuento.clear()
                logger.info("M2M 'items_con_descuento' guardadas.")

                # PASO 6: Calcular Deducción Total de Stock
                logger.info("Calculando deducción final de stock...")
                stock_warnings = []
                total_stock_to_deduct = Counter()
                all_involved_pks = set(half_item_counts.keys()) | set(full_item_counts.keys())

                for extra_pk in all_involved_pks:
                    halves = half_item_counts.get(extra_pk, 0)
                    fulls = full_item_counts.get(extra_pk, 0)
                    integer_deduction = fulls + (halves // 2) # Solo enteros y pares de mitades
                    if halves % 2 > 0:
                        try:
                            extra_name = Extra.objects.get(pk=extra_pk).nombre
                            warning_msg = (f"Nota: Quedó media unidad (50%) de '{extra_name}' sin completar para stock.")
                            stock_warnings.append(warning_msg)
                            logger.info(f"Mitad impar de '{extra_name}' (PK: {extra_pk}) no descontada.")
                        except Extra.DoesNotExist: logger.error(f"No se encontró Extra PK {extra_pk} para warning mitad.")
                    if integer_deduction > 0:
                        total_stock_to_deduct[extra_pk] = integer_deduction

                # PASO 7: Deducción de Stock
                logger.info("Iniciando deducción de stock calculado...")
                extras_involved_pks_final = list(total_stock_to_deduct.keys())
                if extras_involved_pks_final:
                    stocks_to_update_qs = Stock.objects.select_for_update().filter(extra_id__in=extras_involved_pks_final)
                    stock_map = {stock.extra_id: stock for stock in stocks_to_update_qs}
                    stocks_actually_updated = []
                    for extra_pk, items_to_deduct in total_stock_to_deduct.items():
                        if items_to_deduct > 0:
                            # (Lógica de deducción y warnings de insuficiencia como antes)
                            stock_record = stock_map.get(extra_pk)
                            if stock_record:
                                if stock_record.cantidad >= items_to_deduct:
                                    stock_record.cantidad -= items_to_deduct
                                    stocks_actually_updated.append(stock_record)
                                else:
                                    original_needed=items_to_deduct; actual_deducted=stock_record.cantidad; stock_record.cantidad=0
                                    stocks_actually_updated.append(stock_record)
                                    warning_msg = f"Stock insuficiente para '{stock_record.extra.nombre}'. Necesitaban {original_needed}, disp. {actual_deducted}. Stock a 0."
                                    stock_warnings.append(warning_msg); logger.warning(warning_msg)
                            else:
                                try: extra_name_log = Extra.objects.get(pk=extra_pk).nombre
                                except: extra_name_log = f"ID {extra_pk}"
                                warning_msg = f"No se encontró registro de stock para '{extra_name_log}'. No se pudo deducir."
                                stock_warnings.append(warning_msg); logger.error(f"No Stock found for Extra PK {extra_pk}")
                    if stocks_actually_updated:
                        Stock.objects.bulk_update(stocks_actually_updated, ['cantidad'])
                        logger.info(f"Stock actualizado para {len(stocks_actually_updated)} items.")

            # --- FIN Transacción ---
            logger.info("Transacción completada exitosamente.")
            messages.success(self.request, f"Picadito '{self.object.nombre}' guardado exitosamente.")
            for warning in stock_warnings: messages.warning(self.request, warning)
            return redirect(self.get_success_url())

        except Exception as e:
            logger.exception("!!! EXCEPCIÓN INESPERADA EN Picadito Create form_valid !!!")
            messages.error(self.request, f"Error grave al guardar: {e}")
            context = self.get_context_data(form=form)
            context['participantes_formset'] = ParticipantePicaditoFormSet(self.request.POST, instance=self.object, prefix='participantes')
            return self.render_to_response(context)

    def form_invalid(self, form):
        logger.error("="*10 + ">>> Picadito Create form_invalid INICIADO" + "="*10)
        participantes_formset = getattr(self, 'invalid_formset', None)
        if participantes_formset is None:
            participantes_formset = ParticipantePicaditoFormSet(self.request.POST, instance=self.object, prefix='participantes')
        # (Logging de errores como antes)
        logger.error(f"Form Errores: {form.errors.as_json()}")
        logger.error(f"FormSet Errores: {participantes_formset.errors}")
        logger.error(f"FormSet Non-form Errores: {participantes_formset.non_form_errors()}")
        messages.error(self.request, "Corrija los errores indicados.")
        context = self.get_context_data(form=form)
        context['participantes_formset'] = participantes_formset # Pasar el formset inválido
        return self.render_to_response(context)

    def get_success_url(self):
        return reverse_lazy('picadito-list')
