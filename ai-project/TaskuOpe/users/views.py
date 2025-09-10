from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


class FinnishLoginView(LoginView):
    """
    Lisää onnistumisviesti kirjautumisen jälkeen.
    """
    template_name = "registration/login.html"

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
