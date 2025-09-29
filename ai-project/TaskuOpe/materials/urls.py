from django.urls import path
from . import views



urlpatterns = [
    # Dashboard
    path("", views.dashboard_view, name='dashboard'),

    # Yleiset
    path("palautukset/", views.view_all_submissions_view, name="view_all_submissions"),

    # Material URLs
    path("create/", views.create_material_view, name="create_material"),
    path("material/<uuid:material_id>/", views.material_detail_view, name="material_detail"),
    path("material/<uuid:material_id>/assign/", views.assign_material_view, name="assign_material"),
    path("material/<uuid:material_id>/delete/", views.delete_material_view, name="delete_material"),
    path("material/<uuid:material_id>/submissions/", views.view_submissions, name="view_submissions"),
    path("materiaalit/", views.material_list_view, name="material_list"),

    # 🔧 Nämä kaksi muutettu int -> uuid
    path("material/<uuid:material_id>/edit/", views.edit_material_view, name="material_edit"),
    path("material/<uuid:material_id>/add-image/", views.add_material_image_view, name="material_add_image"),

    # Assignment URLs
    path("assignment/<uuid:assignment_id>/", views.assignment_detail_view, name="assignment_detail"),
    path("assignment/<uuid:assignment_id>/delete/", views.delete_assignment_view, name="delete_assignment"),
    path('assignment/<uuid:assignment_id>/unassign/', views.unassign_assignment, name='unassign'),

    # Kuvagenerointi
    path("image/generate/", views.generate_image_view, name="generate_image"),

    # Submission URLs
    path("submission/<uuid:submission_id>/grade/", views.grade_submission_view, name="grade_submission"),

    # Oppilaan näkymät
    path("oppilas/tehtavat/", views.student_assignments_view, name="student_assignments"),
    path("oppilas/palautukset/", views.student_grades_view, name="student_grades"),

    # Automaattitallennus
    path("assignment/<uuid:assignment_id>/autosave/", views.assignment_autosave_view, name="assignment_autosave"),

    # CSV-vienti
    path("palautukset/export.csv", views.export_submissions_csv_view, name="export_submissions_csv"),

    path("materials/images/<int:image_id>/delete/", views.delete_material_image_view,  name="material_image_delete"),
 
    path("materials/<uuid:material_id>/images/<int:image_id>/insert/", views.material_image_insert_view, name="material_image_insert"),

    path('students/', views.teacher_student_list_view, name='teacher_student_list'),
]
