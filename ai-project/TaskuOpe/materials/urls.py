# materials/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # Example URL: /
    path('', views.dashboard_view, name='dashboard'),

    path('create/', views.create_material_view, name='create_material'),
    
    # Example URL: /material/a1b2c3d4-e5f6-..../
    path('material/<uuid:material_id>/', views.material_detail_view, name='material_detail'),
    
    # Example URL: /material/a1b2c3d4-e5f6-..../assign/
    path('material/<uuid:material_id>/assign/', views.assign_material_view, name='assign_material'),

    # Poistot
    path("material/<uuid:material_id>/delete/", views.delete_material_view, name="delete_material"),
    path("assignment/<uuid:assignment_id>/delete/", views.delete_assignment_view, name="delete_assignment"),
]