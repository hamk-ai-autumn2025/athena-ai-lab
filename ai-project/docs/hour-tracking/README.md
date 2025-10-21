# AI Project Hour Tracker

Built by Mirka Romppanen using Gemini 2.5 Pro (temperature set to 2), according to Mirka's specifications.

This is a Python-based GUI tool for logging and tracking working hours in an AI project. The application uses Tkinter for the graphical user interface, and stores data in separate `.csv` files for each team member. A management dashboard shows team and subject summaries, including visualizations.

## NOTE!

Visual date selection has bugs -> Please add date manually

## Update for Version 2

This is Version 2 of the AI Project Hour Tracker, with several improvements:

### What’s New

Added **CSV summary export** to Manager Dashboard -> Project hour summary per person  
UTF-8 BOM encoding used for CSV exports → Better Excel compatibility  
Uses safe ASCII-only filenames to avoid issues with special characters  

## Features

- **Log hours** with your name, date, number of hours, and work subject.
- Each user's records are saved in a dedicated `.csv` file inside the `hour_tracking_files/` subfolder.
- View total project hours, team member summaries, and hours by work subject.
- Visualize data:  
  - Bar chart (weekly hours)  
  - Pie chart (work distribution by member)
- Automatic creation of the data folder and new user files.
- Add new users simply by entering a new name.

## Installation

1. **Clone this repository** and navigate to the folder.
2. **Install requirements**:
    ```
    pip install -r requirements.txt
    ```

3. **Make sure Tkinter is installed:**:
    Windows/Mac -> Tkinter is included in Python

    Linux (Ubuntu/Debian etc.)
    If you get an error like "ModuleNotFoundError: No module named 'tkinter'" when launching the app, install Tkinter using the command above.
    ```
    sudo apt-get update && sudo apt-get install python3-tk
    ```

4. **Run the application**:  
    Linux:  
    ```
    python3 hour_tracker_v2.py
    ```
    Windows:  
    ```
    python hour_tracker_v2.py
    ```



> The program will automatically create the `hour_tracking_files/` folder for storing data files.

## Usage

### Logging Hours

- Enter/select your **full name**.
- Pick the **date**.
- Enter **hours worked** (use decimal format, e.g., `1.5`).
- Select the **work subject**.
- Click **"Log Hours"**.  
  Your data will be saved to your own `.csv` file.

### Manager Dashboard

- Click **"Load/Refresh Project Data"** to update statistics.
- View:
  - **Total project hours**
  - **Hours by team member**
  - **Hours by work subject**
  - **Bar chart** (weekly total hours)
  - **Pie chart** (work distribution by member)

### Notes

- File names are ASCII-only (e.g., non-English letters are converted or removed).
- If the `tkcalendar` library is missing, the app shows an error message with install instructions.

## Requirements

See [`requirements.txt`](./requirements.txt).

- Python 3.8 or higher
- Required libraries:
    - pandas
    - matplotlib
    - tkcalendar

Tkinter is included with most Python distributions. In Linux check the instructions above.

## Data Files
- For summary data, save location is set by the user
- All data is stored in the `hour_tracking_files/` subfolder, which is created in the same directory as the script.
- Each user's file is named `[username]_hours.csv`.

## License

Free to use and modify for any purpose.

---

