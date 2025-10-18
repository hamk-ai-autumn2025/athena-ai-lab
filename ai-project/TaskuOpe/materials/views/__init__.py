# materials/views/__init__.py

from .main import dashboard_view

from .teacher import (
    teacher_dashboard_view, create_material_view, material_list_view, edit_material_view,
    delete_material_view, assign_material_view, unassign_assignment, delete_assignment_view,
    view_submissions, grade_submission_view, view_all_submissions_view,
    export_submissions_csv_view, teacher_student_list_view,
    add_material_image_view,
    delete_material_image_view,
    material_image_insert_view # TÄMÄ ON NYT OIKEIN, KOSKA FUNKTIO ON LISÄTTY
)

from .student import (
    student_dashboard_view, student_assignments_view, student_grades_view,
    student_games_view, assignment_detail_view, play_game_view
)

from .api import (
    generate_game_ajax_view, complete_game_ajax_view, assignment_autosave_view,
    generate_image_view, assignment_tts_view, ops_facets, ops_search
)

from .shared import (
    material_detail_view, render_material_content_to_html,
    format_game_content_for_display
)