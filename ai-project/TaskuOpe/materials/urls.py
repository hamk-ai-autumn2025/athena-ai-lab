from django.urls import path, include
from . import views

urlpatterns = [
    # Dashboard
    path("", views.dashboard_view, name='dashboard'),

    # Materiaalin hallinta
    path("create/", views.create_material_view, name="create_material"),
    path("material/<uuid:material_id>/", views.material_detail_view, name="material_detail"),
    path("material/<uuid:material_id>/assign/", views.assign_material_view, name="assign_material"),
    path("material/<uuid:material_id>/delete/", views.delete_material_view, name="delete_material"),

    # Tehtävien hallinta
    path("assignment/<uuid:assignment_id>/", views.assignment_detail_view, name="assignment_detail"),
    path("assignment/<uuid:assignment_id>/delete/", views.delete_assignment_view, name="delete_assignment"),

    # Palautusten listaus tälle materiaalille
    path('material/<uuid:material_id>/submissions/', views.view_submissions, name='view_submissions'),

    # Yksittäisen palautuksen arviointi
    path('submission/<uuid:submission_id>/grade/', views.grade_submission_view, name='grade_submission'),

    path("material/<uuid:material_id>/submissions/", views.view_submissions, name="view_submissions"),
    path("submission/<uuid:submission_id>/grade/", views.grade_submission_view, name="grade_submission"),

]
