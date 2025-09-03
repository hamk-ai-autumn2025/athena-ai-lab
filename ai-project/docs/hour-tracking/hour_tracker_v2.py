# hour_tracker_gui.py (Final version with UTF-8-BOM for Excel compatibility)
# Generated with GEMINI 2.5 Pro, Temperature 2 with Mirka Romppanen instructions

import os
import csv
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import unicodedata

try:
    from tkcalendar import DateEntry
except ImportError:
    messagebox.showerror(
        "Missing Library",
        "The 'tkcalendar' library is required. Please install it by running:\n\npip install tkcalendar"
    )
    exit()

# --- Configuration & Core Logic ---
SUBJECT_OPTIONS = ["Technical Work", "Meetings", "Data Annotation", "Documentation", "Training Models"]
CSV_HEADER = ['name', 'date', 'hours', 'subject']

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = os.path.join(SCRIPT_DIR, "hour_tracking_files")


def get_employee_filename(name):
    """Generates a safe, ASCII-only filename inside the data subfolder."""
    normalized_name = unicodedata.normalize('NFD', name)
    ascii_name = normalized_name.encode('ascii', 'ignore').decode('ascii')
    safe_filename_base = ascii_name.strip().replace(" ", "_").lower()
    filename = f"{safe_filename_base}_hours.csv"
    
    return os.path.join(DATA_FOLDER, filename)


# --- GUI Application ---
class HourTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Project Hour Tracker")
        self.root.geometry("950x900")
        self.root.minsize(800, 600)

        self.colors = {
            "bg": "#F5F5F5", "accent": "#5C85AD", "text": "#212121",
            "light_gray": "#E0E0E0", "button_text": "#FFFFFF"
        }
        self.root.configure(bg=self.colors['bg'])
        self.style = ttk.Style(self.root)
        self.style.theme_use('clam')
        
        self.style.configure('.', background=self.colors['bg'], foreground=self.colors['text'], fieldbackground='white')
        self.style.configure('TFrame', background=self.colors['bg'])
        self.style.configure('TLabel', background=self.colors['bg'])
        self.style.configure('TNotebook', background=self.colors['bg'], bordercolor=self.colors['light_gray'])
        self.style.configure('TNotebook.Tab', background=self.colors['light_gray'], padding=[10, 5])
        self.style.map('TNotebook.Tab', background=[('selected', self.colors['bg'])])
        self.style.configure('Accent.TButton', background=self.colors['accent'], foreground=self.colors['button_text'])
        self.style.map('Accent.TButton', background=[('active', '#7C9AB8')])

        os.makedirs(DATA_FOLDER, exist_ok=True)
        self.existing_names = self._get_existing_names()

        self.notebook = ttk.Notebook(root, style='TNotebook')
        self.notebook.pack(pady=10, padx=10, expand=True, fill='both')

        self.log_frame = ttk.Frame(self.notebook, padding="20")
        self.notebook.add(self.log_frame, text='Log Your Hours')
        self.create_log_widgets()

        self.manager_frame = ttk.Frame(self.notebook, padding="20")
        self.notebook.add(self.manager_frame, text='Manager Dashboard')
        self.create_manager_widgets()
        
        self.master_df = None

    def _get_existing_names(self):
        names = set()
        try:
            file_list = [f for f in os.listdir(DATA_FOLDER) if f.endswith("_hours.csv")]
        except FileNotFoundError:
            return []
        for filename in file_list:
            full_path = os.path.join(DATA_FOLDER, filename)
            try:
                df = pd.read_csv(full_path, encoding='utf-8')
                if not df.empty and 'name' in df.columns:
                    names.update(df['name'].unique())
            except Exception:
                continue
        return sorted(list(names))
        
    def create_log_widgets(self):
        self.log_frame.columnconfigure((0, 2), weight=1)
        log_container = ttk.LabelFrame(self.log_frame, text="Log New Entry", padding=20)
        log_container.grid(row=0, column=1, pady=20, sticky="n")
        log_container.columnconfigure(1, minsize=300)

        ttk.Label(log_container, text="Your Full Name:").grid(row=0, column=0, padx=5, pady=10, sticky="w")
        self.name_combobox = ttk.Combobox(log_container, values=self.existing_names)
        self.name_combobox.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        ttk.Label(log_container, text="Date (dd-mm-yyyy):").grid(row=1, column=0, padx=5, pady=10, sticky="w")
        self.date_entry = DateEntry(log_container, date_pattern='dd-mm-yyyy', borderwidth=2)
        self.date_entry.grid(row=1, column=1, padx=5, pady=10, sticky="ew")
        
        ttk.Label(log_container, text="Hours Worked:").grid(row=2, column=0, padx=5, pady=10, sticky="w")
        self.hours_entry = ttk.Entry(log_container)
        self.hours_entry.grid(row=2, column=1, padx=5, pady=10, sticky="ew")

        ttk.Label(log_container, text="Work Subject:").grid(row=3, column=0, padx=5, pady=10, sticky="w")
        self.subject_combobox = ttk.Combobox(log_container, values=SUBJECT_OPTIONS, state='readonly')
        self.subject_combobox.grid(row=3, column=1, padx=5, pady=10, sticky="ew")
        if SUBJECT_OPTIONS:
            self.subject_combobox.current(0)
            
        submit_button = ttk.Button(log_container, text="Log Hours", command=self.log_hours, style='Accent.TButton')
        submit_button.grid(row=4, column=1, padx=5, pady=20, sticky="e")
        
    def log_hours(self):
        name = self.name_combobox.get().strip()
        date_str = self.date_entry.get().strip()
        hours_str = self.hours_entry.get().strip()
        subject = self.subject_combobox.get()
        
        if not all([name, date_str, hours_str, subject]):
            messagebox.showerror("Input Error", "All fields are required.")
            return

        try:
            date_obj = datetime.strptime(date_str, "%d-%m-%Y")
        except ValueError:
            messagebox.showerror("Input Error", "Invalid date format. Please use dd-mm-yyyy.")
            return

        try:
            hours = float(hours_str)
            if hours <= 0:
                messagebox.showerror("Input Error", "Hours must be a positive number.")
                return
        except ValueError:
            messagebox.showerror("Input Error", "Hours must be a valid number.")
            return
            
        filename = get_employee_filename(name)
        file_exists = os.path.exists(filename)
        date_to_save = date_obj.strftime("%Y-%m-%d")

        try:
            with open(filename, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                if not file_exists:
                    writer.writerow(CSV_HEADER)
                writer.writerow([name, date_to_save, hours, subject])
            messagebox.showinfo("Success", f"Successfully logged {hours} hours for {name}.")
            self.hours_entry.delete(0, 'end')

            if name not in self.existing_names:
                self.existing_names.append(name)
                self.existing_names.sort()
                self.name_combobox['values'] = self.existing_names
        except IOError as e:
            messagebox.showerror("File Error", f"Could not write to file {filename}.\n{e}")

    def create_manager_widgets(self):
        controls_frame = ttk.Frame(self.manager_frame)
        controls_frame.pack(fill='x', pady=5)
        
        button_container = ttk.Frame(controls_frame)
        button_container.pack(side='left')
        
        refresh_button = ttk.Button(button_container, text="Load/Refresh Project Data", command=self.show_dashboard)
        refresh_button.pack(side='left', padx=(0, 5))
        
        export_button = ttk.Button(button_container, text="Export Summary", command=self.export_summary_to_csv)
        export_button.pack(side='left')

        self.total_hours_label = ttk.Label(controls_frame, text="Total Project Hours: N/A", font=("Helvetica", 12, "bold"))
        self.total_hours_label.pack(side='right', padx=10)

        main_pane = ttk.PanedWindow(self.manager_frame, orient=tk.VERTICAL)
        main_pane.pack(fill='both', expand=True, pady=10)
        self.charts_frame = ttk.Frame(main_pane)
        main_pane.add(self.charts_frame, weight=4)
        summary_pane = ttk.PanedWindow(main_pane, orient=tk.HORIZONTAL)
        main_pane.add(summary_pane, weight=2)
        person_frame = ttk.LabelFrame(summary_pane, text="Hours by Team Member")
        summary_pane.add(person_frame, weight=1)
        self.person_tree = ttk.Treeview(person_frame, columns=('name', 'hours'), show='headings')
        self.person_tree.heading('name', text='Name')
        self.person_tree.heading('hours', text='Total Hours')
        self.person_tree.pack(fill='both', expand=True)
        subject_frame = ttk.LabelFrame(summary_pane, text="Hours by Subject")
        summary_pane.add(subject_frame, weight=1)
        self.subject_tree = ttk.Treeview(subject_frame, columns=('subject', 'hours'), show='headings')
        self.subject_tree.heading('subject', text='Subject')
        self.subject_tree.heading('hours', text='Total Hours')
        self.subject_tree.pack(fill='both', expand=True)
    
    def export_summary_to_csv(self):
        """Creates a summary of hours per person and exports it to a CSV file."""
        if self.master_df is None or self.master_df.empty:
            messagebox.showwarning("No Data", "Please load project data first before exporting.")
            return

        default_filename = f"project_hours_summary_{datetime.now().strftime('%Y-%m-%d')}.csv"
        
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=default_filename,
            title="Save Hours Summary As"
        )
        
        if filepath:
            try:
                summary_df = self.master_df.groupby('name')['hours'].sum().reset_index()
                summary_df.rename(columns={'hours': 'total_hours'}, inplace=True)
                
                # --- THE FIX: Use 'utf-8-sig' to include the BOM for Excel ---
                summary_df.to_csv(filepath, index=False, encoding='utf-8-sig')
                
                messagebox.showinfo("Export Successful", f"Project hours summary has been saved to:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to save the file.\nError: {e}")

    def show_dashboard(self):
        all_data = []
        try:
            file_list = [f for f in os.listdir(DATA_FOLDER) if f.endswith("_hours.csv")]
        except FileNotFoundError:
            messagebox.showinfo("No Data", f"The data folder '{DATA_FOLDER}' was not found.")
            return
        if not file_list:
            messagebox.showinfo("No Data", "No project data files (.csv) found.")
            self.master_df = None
            return

        for filename in file_list:
            full_path = os.path.join(DATA_FOLDER, filename)
            try:
                df = pd.read_csv(full_path, encoding='utf-8')
                if not df.empty: all_data.append(df)
            except Exception as e:
                messagebox.showwarning("File Read Error", f"Could not read {os.path.basename(full_path)}.\nError: {e}")
        
        if not all_data:
            messagebox.showinfo("No Data", "No valid data found in CSV files.")
            self.master_df = None
            return
        
        self.master_df = pd.concat(all_data, ignore_index=True)
        self.master_df['date'] = pd.to_datetime(self.master_df['date'])
        self.update_dashboard_ui()

    def update_dashboard_ui(self):
        total_hours = self.master_df['hours'].sum()
        hours_by_person = self.master_df.groupby('name')['hours'].sum().reset_index()
        hours_by_subject = self.master_df.groupby('subject')['hours'].sum().reset_index()
        self.total_hours_label.config(text=f"Total Project Hours: {total_hours:.2f}")

        for tree in [self.person_tree, self.subject_tree]:
            for i in tree.get_children(): tree.delete(i)
        for _, row in hours_by_person.iterrows(): self.person_tree.insert("", "end", values=(row['name'], f"{row['hours']:.2f}"))
        for _, row in hours_by_subject.iterrows(): self.subject_tree.insert("", "end", values=(row['subject'], f"{row['hours']:.2f}"))
        self.draw_charts(self.master_df, hours_by_person)

    def draw_charts(self, master_df, hours_by_person):
        for widget in self.charts_frame.winfo_children():
            widget.destroy()
        plt.style.use('seaborn-v0_8-whitegrid')
        fig = plt.Figure(figsize=(9, 5), dpi=100, facecolor=self.colors['bg'])
        ax1 = fig.add_subplot(121)
        weekly_hours = master_df.set_index('date').resample('W-MON', label='left')['hours'].sum()
        weekly_hours.index = weekly_hours.index.strftime('%Y-%m-%d')
        weekly_hours.plot(kind='bar', ax=ax1, color=self.colors['accent'], legend=False)
        ax1.set_title('Total Hours per Week', color=self.colors['text'])
        ax1.set_xlabel('Week Start Date', color=self.colors['text'])
        ax1.set_ylabel('Hours', color=self.colors['text'])
        ax1.tick_params(axis='x', rotation=45, labelsize=9, colors=self.colors['text'])
        ax1.tick_params(axis='y', colors=self.colors['text'])
        ax1.grid(True, axis='y', linestyle='--', alpha=0.7)
        for spine in ax1.spines.values(): spine.set_edgecolor(self.colors['light_gray'])
        ax2 = fig.add_subplot(122)
        ax2.pie(hours_by_person['hours'], labels=hours_by_person['name'], autopct='%1.1f%%', startangle=90, textprops={'fontsize': 9, 'color': self.colors['text']})
        ax2.set_title('Work Distribution by Member', color=self.colors['text'])
        ax2.axis('equal')
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self.charts_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

if __name__ == "__main__":
    root = tk.Tk()
    app = HourTrackerApp(root)
    root.mainloop()