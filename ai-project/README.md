# TaskuOpe Project

Developers (group Athena): Mirka Romppanen, Ida-Sofia Kilpi, Inka Kaalikoski and Jiska Laaksovirta

This repository contains the **TaskuOpe** application, developed as part of the AI course in autumn 2025.  

---

## Setup Instructions

1. **Create and activate a virtual environment**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

2. **Install dependencies**
   ```powershell
   pip install -r requirements.txt
   ```

---

## Hour Tracking Application NOTE: Updated real-time project hours at Moodle return!!!
The hour tracking application can be found in its own subdirectory inside this project.  
➡️ Please read the **README.md** file in that directory for specific instructions on setup and usage.
https://github.com/hamk-ai-autumn2025/athena-ai-lab/tree/main/ai-project/docs/hour-tracking

---

## Testing Instructions

To test the application, follow these steps:

1. **Create Django admin credentials**
   Run the following command in the project root:
   ```powershell
   python manage.py createsuperuser
   ```

2. **Access the Django admin panel**
   Start the development server:
   ```powershell
   python manage.py runserver
   ```
   Then go to [http://localhost:8000/admin/](http://localhost:8000/admin/) and log in with the superuser account.

3. Petri Kuittinen - published ip and kayttajat.txt testusers provided via email

---

## Notes



---