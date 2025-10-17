"""
Määrittelee käyttäjien autentikointiin ja profiilin hallintaan liittyvät näkymät.

Tämä tiedosto sisältää luokkapohjaisen näkymän sisäänkirjautumiselle
(FinnishLoginView) sekä funktiopohjaiset näkymät uloskirjautumiselle
(simple_logout) ja käyttäjäprofiilin näyttämiselle (profile_view).
"""

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

# --- NEW: Import the custom form we created ---
from .forms import CustomLoginForm, ProfileImageForm


class FinnishLoginView(LoginView):
    """
    Mukautettu sisäänkirjautumisnäkymä.

    Laajentaa Djangon oletusarvoista LoginView'ta lisäämällä
    onnistumisviestin kirjautumisen jälkeen ja käyttämällä
    mukautettua sisäänkirjautumislomaketta.
    """
    template_name = "registration/login.html"
    
    # --- NEW: Tell this view to use our custom form ---
    authentication_form = CustomLoginForm

    def form_valid(self, form):
        """
        Käsitellään onnistunut lomakkeen lähetys.

        Lisää onnistumisviestin käyttäjälle ja kutsuu yliluokan
        form_valid-metodia jatkamaan kirjautumisprosessia.
        """
        response = super().form_valid(form)
        messages.success(self.request, "Kirjautuminen onnistui. Tervetuloa takaisin!")
        return response


@csrf_exempt
@require_http_methods(["GET", "POST"])
def simple_logout(request):
    """
    Kirjaa käyttäjän ulos ja ohjaa sisäänkirjautumissivulle.

    Tämä näkymä sallii sekä GET- että POST-pyynnöt uloskirjautumiseen
    ja lisää ilmoitusviestin uloskirjautumisesta.
    """
    """
    Kirjaa ulos GET- tai POST-pyynnöllä ja ohjaa aina /kirjaudu.
    """
    logout(request)
    messages.info(request, "Olet kirjautunut ulos.")
    return redirect("kirjaudu")

@login_required(login_url='kirjaudu')
def profile_view(request):
    """
    Näyttää käyttäjän profiilin ja käsittelee profiilikuvan päivityksen.
    """
    if request.method == 'POST':
        # Käsitellään kuvan lataus
        form = ProfileImageForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profiilikuva päivitetty onnistuneesti!")
            return redirect('profile')
    else:
        # Näytetään tyhjä lomake
        form = ProfileImageForm(instance=request.user)

    context = {
        'user': request.user,
        'form': form  # Välitetään lomake templatelle
    }
    return render(request, 'registration/profile.html', context)