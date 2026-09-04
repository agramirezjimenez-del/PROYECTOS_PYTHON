from django.shortcuts import render, redirect
from .forms import UserRegisterForm
from django.contrib import messages

#vista para el registrar un nuevo usuario
def register_view(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save() #guarda el nuevo usuario en la base de datos
            username = form.cleaned_data.get('username')
            messages.success(request, f'Usuario {username} creado exitosamente.')
            return redirect('login') #redirecciona a la pagina de login despues de registrar
        else:
            messages.error(request, 'Por favor, corrija los errores en el formulario.')
    else:
        form = UserRegisterForm()
    return render(request, 'accounts/register.html', {'form': form})
