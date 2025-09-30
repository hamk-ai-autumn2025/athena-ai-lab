from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

# --- NEW: Import the custom form we created ---
from .forms import CustomLoginForm


class FinnishLoginView(LoginView):
    """
    Lisää onnistumisviesti kirjautumisen jälkeen.
    """
    template_name = "registration/login.html"
    
    # --- NEW: Tell this view to use our custom form ---
    authentication_form = CustomLoginForm

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Kirjautuminen onnistui. Tervetuloa takaisin!")
        return response


@csrf_exempt
@require_http_methods(["GET", "POST"])
def simple_logout(request):
    """
    Kirjaa ulos GET- tai POST-pyynnöllä ja ohjaa aina /kirjaudu.
    """
    logout(request)
    messages.info(request, "Olet kirjautunut ulos.")
    return redirect("kirjaudu")

@login_required(login_url='kirjaudu')
def profile_view(request):
    """Näyttää sisäänkirjautuneen käyttäjän profiilisivun."""
    
    # Haetaan käyttäjä suoraan pyynnöstä. Ei tarvitse hakea tietokannasta.
    user = request.user

    # Välitetään käyttäjäobjekti templatelle 'user'-nimisessä kontekstimuuttujassa.
    context = {
        'user': user
    }

    # Pyydetään Djangoa renderöimään 'profile.html'-sivu ja antamaan sille data.
    return render(request, 'registration/profile.html', context)