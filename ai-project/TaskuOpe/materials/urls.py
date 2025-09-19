from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path("", views.dashboard_view, name='dashboard'),

    # --- THIS IS THE NEW URL ---
    path("palautukset/", views.view_all_submissions_view, name="view_all_submissions"),

    # Material URLs
    path("create/", views.create_material_view, name="create_material"),
    path("material/<uuid:material_id>/", views.material_detail_view, name="material_detail"),
    path("material/<uuid:material_id>/assign/", views.assign_material_view, name="assign_material"),
    path("material/<uuid:material_id>/delete/", views.delete_material_view, name="delete_material"),
    path('material/<uuid:material_id>/submissions/', views.view_submissions, name='view_submissions'),
    path("materiaalit/", views.material_list_view, name="material_list"),

    # Assignment URLs
    path("assignment/<uuid:assignment_id>/", views.assignment_detail_view, name="assignment_detail"),
    path("assignment/<uuid:assignment_id>/delete/", views.delete_assignment_view, name="delete_assignment"),

    # Submission URLs
    path('submission/<uuid:submission_id>/grade/', views.grade_submission_view, name='grade_submission'),

     # --- Oppilaan näkymät ---
    path("oppilas/tehtavat/", views.student_assignments_view, name="student_assignments"),
    path("oppilas/palautukset/", views.student_grades_view, name="student_grades"),

    # Automaattitallennus
    path("assignment/<uuid:assignment_id>/autosave/", views.assignment_autosave_view, name="assignment_autosave"),

    path("palautukset/export.csv", views.export_submissions_csv_view, name="export_submissions_csv"),
]