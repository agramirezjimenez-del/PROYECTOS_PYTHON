from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')), #incluir las rutas de la 
    #aplicacion autenticacion
    path('', include('django.contrib.auth.urls')), #incluir las vistas predefinidas de 
    #autenticacion de django
]
