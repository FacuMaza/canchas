from django.urls import path
from canchas import views
from django.contrib.auth import views as auth_views
from .views import *



urlpatterns = [
    path('', views.PublicHomeView.as_view(), name='public-home'),
    path('dashboard/', views.dashboard, name="dashboard"),
    path('home/', HomeView.as_view(), name='home'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('reservar-turno/<int:cancha_pk>/<str:fecha>/', views.PublicReservarClienteView.as_view(), name='public-reservar-cliente'),
    path('reserva-exitosa/', views.ReservaExitosaView.as_view(), name='reserva-exitosa'),
]


## RECUPERAR CONTRASEÑA

urlpatterns += [
     path('reset_password/', 
     auth_views.PasswordResetView.as_view(
         template_name="password_reset_form.html",
         email_template_name="password_reset_email.html",
         subject_template_name="password_reset_subject.txt"
     ), 
     name="password_reset"),
    path('reset_password/done/', 
         auth_views.PasswordResetDoneView.as_view(template_name="password_reset_done.html"), 
         name="password_reset_done"),
    path('reset/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(template_name="password_reset_confirm.html"), 
         name="password_reset_confirm"),
    path('reset/done/', 
         auth_views.PasswordResetCompleteView.as_view(template_name="password_reset_complete.html"), 
         name="password_reset_complete"),
]


##CREAR CUENTAS 

urlpatterns += [
    path('accounts/', views.UserListView.as_view(), name='user-list'),
    path('accounts/create/', views.UserCreateView.as_view(), name='user-create'),
    path('accounts/<int:pk>/update/', views.UserUpdateView.as_view(), name='user-update'),
    path('accounts/<int:pk>/delete/', views.UserDeleteView.as_view(), name='user-delete'),

]




 ## CREAR CANCHAS
urlpatterns += [
    # URLs para Canchas
    path('canchas/', views.CanchaListView.as_view(), name='cancha-list'),
    path('canchas/nueva/', views.CanchaCreateView.as_view(), name='cancha-create'),
    path('canchas/<int:pk>/', views.CanchaDetailView.as_view(), name='cancha-detail'),
    path('canchas/<int:pk>/editar/', views.CanchaUpdateView.as_view(), name='cancha-update'),
    path('canchas/<int:pk>/eliminar/', views.CanchaDeleteView.as_view(), name='cancha-delete'),

]


##HORARIOS DE CANCHAS
urlpatterns += [
 
    path('canchas/<int:cancha_pk>/horarios/nuevo/', views.HorarioDisponibleCreateView.as_view(), name='horario-create'),
    path('horarios/<int:pk>/editar/', views.HorarioDisponibleUpdateView.as_view(), name='horario-update'),
    path('horarios/<int:pk>/eliminar/', views.HorarioDisponibleDeleteView.as_view(), name='horario-delete'),
]


##RESERVAS

urlpatterns += [
   path('reservar/<int:cancha_pk>/<str:fecha>/', views.ReservarFechaView.as_view(), name='reservar-fecha'),
   path('reservas/cancelar/<int:reserva_pk>/', views.CancelarReservaView.as_view(), name='cancelar-reserva'),
]

##COBROS
urlpatterns += [
    path('cobro/reserva/<int:reserva_pk>/', views.CobroReservaView.as_view(), name='cobro-reserva'),
]


##CIERRE DE CAJA
urlpatterns += [
    path('cierre-caja/', views.CierreCajaView.as_view(), name='cierre-caja'),
    path('cierre-caja/realizar/', views.RealizarCierreCajaView.as_view(), name='realizar-cierre-caja'),
    path('cierre-caja/historial/', views.HistorialCierreCajaView.as_view(), name='historial-cierre-caja'),
    path('cierre-caja/detalle/<int:pk>/', views.CierreCajaDetalleView.as_view(), name='cierre-caja-detalle'),
     path('cierre-caja/detalle/<int:pk>/descargar/pdf/', views.DescargarCierreCajaPDFView.as_view(), name='descargar-cierre-caja-pdf'),
     path('cierre-caja/generales/', views.CierreCajaGeneralListView.as_view(), name='cierre-caja-generales'),
]


##EXTRAS
urlpatterns += [
    path('movimientos/', views.MovimientosRecientesListView.as_view(), name='movimientos-list'),
    path('extras/nuevo/', views.ExtraCreateView.as_view(), name='extra-create'),
    path('extras/<int:pk>/editar/', views.ExtraUpdateView.as_view(), name='extra-update'),
    path('extras/<int:pk>/eliminar/', views.ExtraDeleteView.as_view(), name='extra-delete'),
]


##INGRESOS
urlpatterns += [
    path('ingresos/', views.IngresoListView.as_view(), name='ingreso-list'),
    path('ingresos/nuevo/', views.IngresoCreateView.as_view(), name='ingreso-create'),
]

##HISTORIAL
urlpatterns += [
    path('historial/', views.HistorialView.as_view(), name='historial-view'),
    path('movimiento/nuevo/', views.MovimientoRapidoCreateView.as_view(), name='movimiento-rapido-create'),
    path('resumenes/', views.ResumenesView.as_view(), name='resumenes-view'),
    path('historial/diario/<str:fecha_str>/', views.HistorialDiarioDetalleView.as_view(), name='historial-diario-detalle'),
    path('historial/mensual/<int:year>/<int:month>/', views.HistorialMensualDetalleView.as_view(), name='historial-mensual-detalle'),
    path('historial/anual/<int:year>/', views.HistorialAnualDetalleView.as_view(), name='historial-anual-detalle'),
    path('historial/diario/<str:fecha_str>/descargar/pdf/', views.DescargarHistorialDiarioPDFView.as_view(), name='descargar-historial-diario-pdf'),
    path('historial/mensual/<int:year>/<int:month>/descargar/pdf/', views.DescargarHistorialMensualPDFView.as_view(), name='descargar-historial-mensual-pdf'),
    path('historial/anual/<int:year>/descargar/pdf/', views.DescargarHistorialAnualPDFView.as_view(), name='descargar-historial-anual-pdf'),
]




##egreso
urlpatterns += [
    path('egresos/', views.EgresoListView.as_view(), name='egreso-list'),
    path('egresos/nuevo/', views.EgresoCreateView.as_view(), name='egreso-create'),

]


##stock

urlpatterns += [
    
    path('stock/cargar/', views.StockCargarView.as_view(), name='stock_cargar'),
    path('stock/listar/', views.StockListView.as_view(), name='stock_listar'),
    path('stock/editar/<int:pk>/', views.StockEditarView.as_view(), name='stock_editar'),
    path('stock/<int:pk>/eliminar/', views.stock_eliminar, name='stock_eliminar'),
    
    
    path('ventas/registrar/', views.VentaCreateView.as_view(), name='venta_registrar'),
    path('ventas/listar/', views.VentaListView.as_view(), name='venta_listar'),

]


## picaditos

urlpatterns += [
    
    path('picaditos/', views.PicaditoListView.as_view(), name='picadito-list'),
    path('picaditos/nuevo/', views.PicaditoCreateSimplifiedView.as_view(), name='picadito-create'),
    path('picaditos/<int:pk>/', views.PicaditoDetailView.as_view(), name='picadito-detail'),

]