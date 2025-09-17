import os
import shutil

# Base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
OLD_MATERIALS_DIR = os.path.join(BASE_DIR, "materials", "templates", "materials")

# New folder structure
FOLDERS = {
    "dashboard": ["student_dashboard.html", "teacher_dashboard.html"],
    "materials": ["create_material.html", "material_list.html", "material_detail.html"],
    "assignments": [
        "assign_material.html",
        "assignment_detail.html",
        "grade_submission.html",
        "view_all_submissions.html",
        "view_submissions.html",
    ],
}

# Rename map: old → new filenames
RENAME_MAP = {
    "student_dashboard.html": "student.html",
    "teacher_dashboard.html": "teacher.html",
    "create_material.html": "create.html",
    "material_list.html": "list.html",
    "material_detail.html": "detail.html",
    "assign_material.html": "assign.html",
    "assignment_detail.html": "detail.html",
    "grade_submission.html": "grade.html",
    "view_all_submissions.html": "submissions_list.html",
    "view_submissions.html": "student_submissions.html",
}

# Dry-run mode: Set to False when ready to actually move files
DRY_RUN = False  

# 1. Show what folders will be created
for folder in FOLDERS.keys():
    path = os.path.join(TEMPLATES_DIR, folder)
    if DRY_RUN:
        print(f"[DRY-RUN] Would create folder: {path}")
    else:
        os.makedirs(path, exist_ok=True)

# 2. Show what files will be moved
for folder, files in FOLDERS.items():
    for filename in files:
        old_path = os.path.join(OLD_MATERIALS_DIR, filename)
        if os.path.exists(old_path):
            new_name = RENAME_MAP[filename]
            new_path = os.path.join(TEMPLATES_DIR, folder, new_name)
            if DRY_RUN:
                print(f"[DRY-RUN] Would move {old_path} → {new_path}")
            else:
                shutil.move(old_path, new_path)
                print(f"Moved {filename} → {folder}/{new_name}")

# 3. Show what references will be updated
SEARCH_PATHS = [BASE_DIR]  # project root

def preview_references(root_path):
    for root, _, files in os.walk(root_path):
        for file in files:
            if file.endswith(".html") or file.endswith(".py"):
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                for old_name, new_name in RENAME_MAP.items():
                    for folder in FOLDERS.keys():
                        old_ref = f"materials/{old_name}"
                        new_ref = f"{folder}/{new_name}"
                        if old_ref in content:
                            if DRY_RUN:
                                print(f"[DRY-RUN] Would update reference in {file_path}: {old_ref} → {new_ref}")
                            else:
                                content = content.replace(old_ref, new_ref)

                if not DRY_RUN:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)

for path in SEARCH_PATHS:
    preview_references(path)

if DRY_RUN:
    print("\n✅ Dry-run complete. No changes were made.")
    print("   Set DRY_RUN = False to apply changes.")
else:
    print("\n✅ Template migration complete! All references updated.")