# TaskuOpe/urls.py

from django.contrib import admin
from django.urls import path, include

# Import the views from the 'users' app now
from users.views import FinnishLoginView, simple_logout

urlpatterns = [
    path('admin/', admin.site.urls),

    # These paths now correctly use the views from the users app
    path('kirjaudu/', FinnishLoginView.as_view(), name='kirjaudu'),
    path('ulos/', simple_logout, name='ulos'),

    # Include the materials app URLs
    path('', include('materials.urls')), 

]