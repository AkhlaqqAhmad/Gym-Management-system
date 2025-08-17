import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
from datetime import datetime, timedelta
import re
import logging
import os
from PIL import Image, ImageTk
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import openpyxl
import csv
import db

logging.basicConfig(filename='gym.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

class GymManagementSystem:
    def __init__(self, root):
        self.root = root
        self.root.title("Gym Management System")
        self.root.geometry("1200x800")
        
        try:
            db_path = 'gym.db'
            db.initialize_database(db_path)
            self.conn = sqlite3.connect(db_path)
            self.cursor = self.conn.cursor()
            
            # Verify members table schema
            expected_columns = {
                'user_id': 'TEXT',
                'name': 'TEXT',
                'contact': 'TEXT',
                'cnic': 'TEXT',
                'location': 'TEXT',
                'designation': 'TEXT',
                'join_date': 'TEXT',
                'expiry_date': 'TEXT',
                'sport_category': 'TEXT',
                'membership_type': 'TEXT',
                'has_treadmill': 'INTEGER',
                'base_fee': 'REAL',
                'total_fee': 'REAL',
                'is_active': 'INTEGER',
                'updated_at': 'TEXT',
                'photo_path': 'TEXT'
            }
            self.cursor.execute("PRAGMA table_info(members)")
            actual_columns = {col[1]: col[2] for col in self.cursor.fetchall()}
            if actual_columns != expected_columns:
                messagebox.showerror("Error", "Database schema mismatch. Please recreate the database.")
                raise SystemExit
            
            self.setup_ui()
            self.update_total_fees()
            self.load_members()
            
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Database error: {str(e)}")
            logging.error(f"Initialization failed: {str(e)}")
            raise SystemExit

    def update_total_fees(self):
        try:
            self.cursor.execute("SELECT user_id, base_fee, has_treadmill, total_fee FROM members")
            members = self.cursor.fetchall()
            for member in members:
                expected_fee = member[1] + (400 if member[2] else 0)
                if member[3] != expected_fee:
                    self.cursor.execute("UPDATE members SET total_fee=?, updated_at=? WHERE user_id=?", 
                                      (expected_fee, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), member[0]))
            self.conn.commit()
        except sqlite3.Error as e:
            logging.error(f"Total fee update failed: {str(e)}")

    def setup_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True)
        
        self.member_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.member_frame, text='Member Management')
        self.create_member_management_tab()
        
        self.payment_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.payment_frame, text='Record Payment')
        self.create_payment_tab()
        
        self.view_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.view_frame, text='View Members')
        self.create_view_tab()
        
        self.report_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.report_frame, text='Reports')
        self.create_report_tab()

    def create_member_management_tab(self):
        # Create a canvas and scrollbar for left_frame
        left_frame = ttk.Frame(self.member_frame)
        left_frame.pack(side='left', fill='both', padx=10, pady=10, expand=True)
        
        canvas = tk.Canvas(left_frame)
        scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Search Frame
        search_frame = ttk.LabelFrame(scrollable_frame, text="Search Member")
        search_frame.pack(fill='x', pady=5)
        
        ttk.Label(search_frame, text="User ID or CNIC:").pack(side='left', padx=5)
        self.search_member_entry = ttk.Entry(search_frame)
        self.search_member_entry.pack(side='left', padx=5, expand=True, fill='x')
        ttk.Button(search_frame, text="Search", command=self.search_members).pack(side='left', padx=5)
        
        # Search Results
        self.search_results = ttk.Treeview(scrollable_frame, columns=('User ID', 'Name', 'CNIC', 'Plan'), show='headings')
        self.search_results.heading('User ID', text='User ID')
        self.search_results.heading('Name', text='Name')
        self.search_results.heading('CNIC', text='CNIC')
        self.search_results.heading('Plan', text='Plan')
        self.search_results.column('User ID', width=80)
        self.search_results.column('Name', width=120)
        self.search_results.column('CNIC', width=120)
        self.search_results.column('Plan', width=80)
        self.search_results.pack(fill='x', pady=5)
        
        actions_frame = ttk.Frame(scrollable_frame)
        actions_frame.pack(fill='x', pady=5)
        ttk.Button(actions_frame, text="View", command=self.view_search_result).pack(side='left', padx=5)
        ttk.Button(actions_frame, text="Update", command=self.load_for_update).pack(side='left', padx=5)
        ttk.Button(actions_frame, text="Delete", command=self.delete_from_search).pack(side='left', padx=5)
        ttk.Button(actions_frame, text="Pay", command=self.redirect_to_payment).pack(side='left', padx=5)
        
        # Member Form
        form_frame = ttk.LabelFrame(scrollable_frame, text="Member Form")
        form_frame.pack(fill='both', pady=10)
        
        fields = [
            ("User ID", "user_id"),
            ("Name", "name"),
            ("Contact", "contact"),
            ("CNIC", "cnic"),
            ("Location", "location"),
            ("Designation", "designation"),
            ("Join Date (YYYY-MM-DD)", "join_date"),
            ("Expiry Date (YYYY-MM-DD)", "expiry_date"),
            ("Base Fee", "base_fee")
        ]
        
        self.member_entries = {}
        for i, (label, field) in enumerate(fields):
            ttk.Label(form_frame, text=label+":").grid(row=i, column=0, padx=5, pady=2, sticky='e')
            entry = ttk.Entry(form_frame)
            entry.grid(row=i, column=1, padx=5, pady=2, sticky='we')
            self.member_entries[field] = entry
        
        ttk.Label(form_frame, text="Sport Category:").grid(row=9, column=0, padx=5, pady=2, sticky='e')
        self.sport_var = tk.StringVar(value="Gym")
        sports = ["Gym", "Basketball", "Long Tennis", "Squash"]
        sport_combo = ttk.Combobox(form_frame, textvariable=self.sport_var, values=sports, state='readonly')
        sport_combo.grid(row=9, column=1, sticky='we', padx=5, pady=2)
        sport_combo.bind('<<ComboboxSelected>>', lambda e: logging.info(f"Sport selected: {self.sport_var.get()}"))
        
        ttk.Label(form_frame, text="Membership Type:").grid(row=10, column=0, padx=5, pady=2, sticky='e')
        self.membership_var = tk.StringVar(value="30-day")
        membership_types = ["15-day", "30-day"]
        membership_combo = ttk.Combobox(form_frame, textvariable=self.membership_var, values=membership_types, state='readonly')
        membership_combo.grid(row=10, column=1, sticky='we', padx=5, pady=2)
        
        self.treadmill_var = tk.BooleanVar()
        ttk.Checkbutton(form_frame, text="Includes Treadmill (+400)", 
                       variable=self.treadmill_var).grid(row=11, column=1, sticky='w', padx=5, pady=2)
        
        ttk.Label(form_frame, text="Photo:").grid(row=12, column=0, padx=5, pady=2, sticky='e')
        self.photo_label = ttk.Label(form_frame, text="No photo selected")
        self.photo_label.grid(row=12, column=1, sticky='w', padx=5, pady=2)
        ttk.Button(form_frame, text="Upload Photo", command=self.upload_photo).grid(row=13, column=1, sticky='w', padx=5, pady=2)
        
        # Button frame for Save, Update, Delete, Clear
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=14, column=0, columnspan=2, pady=10, sticky='we')
        btn_frame.columnconfigure(0, weight=1)
        
        ttk.Button(btn_frame, text="Save", command=self.save_member).grid(row=0, column=0, padx=5, pady=5, sticky='e')
        ttk.Button(btn_frame, text="Update", command=self.update_member).grid(row=0, column=1, padx=5, pady=5, sticky='e')
        ttk.Button(btn_frame, text="Delete", command=self.delete_member).grid(row=0, column=2, padx=5, pady=5, sticky='e')
        ttk.Button(btn_frame, text="Clear", command=self.clear_member_form).grid(row=0, column=3, padx=5, pady=5, sticky='e')
        
        # Member List
        list_frame = ttk.LabelFrame(self.member_frame, text="Member List")
        list_frame.pack(side='right', fill='both', padx=10, pady=10, expand=True)
        
        self.members_tree = ttk.Treeview(list_frame, columns=(
            '#', 'User ID', 'Name', 'Contact', 'CNIC', 'Location', 'Designation', 
            'Join Date', 'Expiry Date', 'Sport', 'Plan', 'Treadmill', 'Base Fee', 'Total Fee'
        ), show='headings')
        
        columns = {
            '#': 50,
            'User ID': 80,
            'Name': 120,
            'Contact': 100,
            'CNIC': 120,
            'Location': 100,
            'Designation': 100,
            'Join Date': 100,
            'Expiry Date': 100,
            'Sport': 80,
            'Plan': 80,
            'Treadmill': 80,
            'Base Fee': 80,
            'Total Fee': 80
        }
        
        for col, width in columns.items():
            self.members_tree.heading(col, text=col)
            self.members_tree.column(col, width=width)
        
        self.members_tree.pack(fill='both', expand=True)
        self.members_tree.bind('<<TreeviewSelect>>', self.load_selected_member)

        # Bind mouse wheel to canvas scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def upload_photo(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.png")])
        if file_path:
            try:
                file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
                if file_size > 2:
                    messagebox.showwarning("Warning", "Image must be less than 2MB")
                    return
                self.photo_path = file_path
                self.photo_label.config(text=os.path.basename(file_path))
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load photo: {str(e)}")
                logging.error(f"Photo upload failed: {str(e)}")

    def create_payment_tab(self):
        frame = ttk.LabelFrame(self.payment_frame, text="Record Payment")
        frame.pack(fill='both', padx=10, pady=10, expand=True)
        
        search_frame = ttk.Frame(frame)
        search_frame.pack(fill='x', pady=5)
        
        ttk.Label(search_frame, text="Search Member (User ID or CNIC):").pack(side='left', padx=5)
        self.search_entry = ttk.Entry(search_frame)
        self.search_entry.pack(side='left', padx=5, expand=True, fill='x')
        
        ttk.Button(search_frame, text="Search", command=self.search_member).pack(side='left', padx=5)
        
        info_frame = ttk.Frame(frame)
        info_frame.pack(fill='x', pady=10)
        
        self.member_info = tk.Text(info_frame, height=7, width=80, state='disabled')
        self.member_info.pack(side='left')
        
        payment_form = ttk.Frame(frame)
        payment_form.pack(fill='x', pady=10)
        
        ttk.Label(payment_form, text="Membership Type:").pack(side='left', padx=5)
        self.payment_membership_var = tk.StringVar()
        ttk.Combobox(payment_form, textvariable=self.payment_membership_var, 
                     values=["15-day", "30-day"], state='readonly').pack(side='left', padx=5)
        
        ttk.Label(payment_form, text="Amount:").pack(side='left', padx=5)
        self.amount_entry = ttk.Entry(payment_form, width=10)
        self.amount_entry.pack(side='left', padx=5)
        
        ttk.Label(payment_form, text="Month (YYYY-MM):").pack(side='left', padx=5)
        self.month_entry = ttk.Entry(payment_form, width=15)
        self.month_entry.pack(side='left', padx=5)
        next_month = (datetime.now() + timedelta(days=30)).strftime("%Y-%m")
        self.month_entry.insert(0, next_month)
        
        ttk.Button(payment_form, text="Record Payment", 
                  command=self.record_payment).pack(side='left', padx=10)
        
        history_frame = ttk.Frame(frame)
        history_frame.pack(fill='both', expand=True)
        
        self.payment_history = ttk.Treeview(history_frame, columns=('ID', 'Date', 'Amount', 'Month', 'Period'), show='headings')
        self.payment_history.heading('ID', text='Payment ID')
        self.payment_history.heading('Date', text='Date')
        self.payment_history.heading('Amount', text='Amount')
        self.payment_history.heading('Month', text='Month')
        self.payment_history.heading('Period', text='Period')
        
        self.payment_history.column('ID', width=80)
        self.payment_history.column('Date', width=100)
        self.payment_history.column('Amount', width=100)
        self.payment_history.column('Month', width=100)
        self.payment_history.column('Period', width=100)
        
        self.payment_history.pack(fill='both', expand=True)

    def create_view_tab(self):
        self.view_tree = ttk.Treeview(self.view_frame, 
                                    columns=('#', 'User ID', 'Name', 'Contact', 'Sport', 'Plan', 'Treadmill', 'Base Fee', 'Total Fee', 'Last Payment'), 
                                    show='headings')
        
        columns = {
            '#': 50,
            'User ID': 80,
            'Name': 150,
            'Contact': 100,
            'Sport': 80,
            'Plan': 80,
            'Treadmill': 80,
            'Base Fee': 80,
            'Total Fee': 80,
            'Last Payment': 120
        }
        
        for col, width in columns.items():
            self.view_tree.heading(col, text=col)
            self.view_tree.column(col, width=width)
        
        self.view_tree.pack(fill='both', expand=True, padx=10, pady=10)
        
        ttk.Button(self.view_frame, text="Refresh", command=self.load_view_tab).pack(pady=5)

    def create_report_tab(self):
        frame = ttk.LabelFrame(self.report_frame, text="Generate Reports")
        frame.pack(fill='both', padx=10, pady=10, expand=True)
        
        controls_frame = ttk.Frame(frame)
        controls_frame.pack(fill='x', pady=5)
        
        ttk.Label(controls_frame, text="Report Type:").pack(side='left', padx=5)
        self.report_type_var = tk.StringVar()
        report_types = ["All Members", "30-Day Plan", "15-Day Plan", "Sport Category", "Expired Members"]
        ttk.Combobox(controls_frame, textvariable=self.report_type_var, values=report_types, 
                     state='readonly').pack(side='left', padx=5)
        self.report_type_var.trace('w', self.toggle_sport_filter)
        
        ttk.Label(controls_frame, text="Month:").pack(side='left', padx=5)
        self.month_var = tk.StringVar()
        months = self.get_available_months()
        ttk.Combobox(controls_frame, textvariable=self.month_var, values=months, 
                     state='readonly').pack(side='left', padx=5)
        
        self.sport_frame = ttk.Frame(controls_frame)
        ttk.Label(self.sport_frame, text="Sport:").pack(side='left', padx=5)
        self.sport_var_report = tk.StringVar()
        sports = ["All", "Gym", "Basketball", "Long Tennis", "Squash"]
        ttk.Combobox(self.sport_frame, textvariable=self.sport_var_report, values=sports, 
                     state='readonly').pack(side='left', padx=5)
        
        ttk.Button(controls_frame, text="Generate", command=self.generate_report).pack(side='left', padx=10)
        
        export_frame = ttk.Frame(frame)
        export_frame.pack(fill='x', pady=5)
        ttk.Button(export_frame, text="Export PDF", command=lambda: self.export_report('pdf')).pack(side='left', padx=5)
        ttk.Button(export_frame, text="Export XLSX", command=lambda: self.export_report('xlsx')).pack(side='left', padx=5)
        ttk.Button(export_frame, text="Export CSV", command=lambda: self.export_report('csv')).pack(side='left', padx=5)
        
        self.summary_label = ttk.Label(frame, text="")
        self.summary_label.pack(fill='x', pady=5)
        
        self.report_tree = ttk.Treeview(frame, show='headings')
        self.report_tree.pack(fill='both', expand=True, padx=5, pady=5)

    def get_available_months(self):
        try:
            self.cursor.execute("SELECT DISTINCT month FROM payments ORDER BY month")
            months = [row[0] for row in self.cursor.fetchall()]
            current = datetime.now()
            for i in range(-12, 13):
                m = (current + timedelta(days=30*i)).strftime("%Y-%m")
                if m not in months:
                    months.append(m)
            return sorted(months)
        except sqlite3.Error as e:
            logging.error(f"Get available months failed: {str(e)}")
            return [datetime.now().strftime("%Y-%m")]

    def toggle_sport_filter(self, *args):
        if self.report_type_var.get() == "Sport Category":
            self.sport_frame.pack(side='left', padx=5)
        else:
            self.sport_frame.pack_forget()

    def generate_report(self):
        report_type = self.report_type_var.get()
        month = self.month_var.get()
        sport = self.sport_var_report.get() if report_type == "Sport Category" else None
        
        if not report_type or not month:
            messagebox.showwarning("Warning", "Please select report type and month")
            return
            
        for row in self.report_tree.get_children():
            self.report_tree.delete(row)
        
        try:
            if report_type == "Expired Members":
                self.generate_expired_report(month)
            else:
                self.generate_payment_report(report_type, month, sport)
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Report generation failed: {str(e)}")
            logging.error(f"Report generation failed: {str(e)}")

    def generate_payment_report(self, report_type, month, sport):
        query = '''
            SELECT p.id, m.user_id, m.name, m.cnic, m.contact, m.sport_category, 
                   m.membership_type, p.amount, p.payment_date, p.period, 
                   m.has_treadmill
            FROM payments p
            JOIN members m ON p.user_id = m.user_id
            WHERE p.month = ?
        '''
        params = [month]
        
        if report_type == "30-Day Plan":
            query += " AND m.membership_type = '30-day'"
        elif report_type == "15-Day Plan":
            query += " AND m.membership_type = '15-day'"
        elif report_type == "Sport Category" and sport != "All":
            query += " AND m.sport_category = ?"
            params.append(sport)
            
        self.cursor.execute(query, params)
        data = self.cursor.fetchall()
        
        if not data:
            messagebox.showinfo("No Data", "No payments found for selected criteria")
            self.summary_label.config(text="")
            return
            
        total_revenue = sum(row[7] for row in data)
        member_count = len(set(row[1] for row in data))
        
        if report_type == "Sport Category":
            self.report_tree["columns"] = ('Sport', 'User ID', 'Name', 'CNIC', 'Contact', 'Plan', 
                                        'Amount', 'Date', 'Period', 'Treadmill')
            self.report_tree.heading('Sport', text='Sport')
            self.report_tree.column('Sport', width=80)
        else:
            self.report_tree["columns"] = ('User ID', 'Name', 'CNIC', 'Contact', 'Sport', 'Plan', 
                                        'Amount', 'Date', 'Period', 'Treadmill')
            
        for col in self.report_tree["columns"]:
            self.report_tree.heading(col, text=col)
            self.report_tree.column(col, width=100 if col in ['Amount', 'Date', 'Period', 'Treadmill'] else 120)
            
        for row in data:
            values = (
                row[5], row[1], row[2], row[3], row[4], row[6], f"Rs {row[7]:.2f}", row[8], 
                row[9] or 'Full Month', 'Yes' if row[10] else 'No'
            ) if report_type == "Sport Category" else (
                row[1], row[2], row[3], row[4], row[5], row[6], f"Rs {row[7]:.2f}", row[8], 
                row[9] or 'Full Month', 'Yes' if row[10] else 'No'
            )
            self.report_tree.insert('', 'end', values=values)
            
        summary = f"Total Revenue: Rs {total_revenue:.2f}, Payments: {len(data)}, Unique Members: {member_count}"
        self.summary_label.config(text=summary)
        self.current_report_data = {
            'type': report_type,
            'month': month,
            'sport': sport,
            'data': data,
            'summary': summary
        }

    def generate_expired_report(self, month):
        year, mon = map(int, month.split('-'))
        next_month = datetime(year, mon + 1, 1) if mon < 12 else datetime(year + 1, 1, 1)
        end_date = next_month.strftime("%Y-%m-%d")
        
        query = '''
            SELECT m.user_id, m.name, m.cnic, m.contact, m.sport_category, 
                   m.membership_type, m.expiry_date, 
                   (SELECT MAX(payment_date) FROM payments p WHERE p.user_id = m.user_id)
            FROM members m
            WHERE m.expiry_date < ? AND m.is_active = 1
        '''
        self.cursor.execute(query, (end_date,))
        data = self.cursor.fetchall()
        
        if not data:
            messagebox.showinfo("No Data", "No expired members found")
            self.summary_label.config(text="")
            return
            
        self.report_tree["columns"] = ('User ID', 'Name', 'CNIC', 'Contact', 'Sport', 
                                     'Plan', 'Expiry Date', 'Last Payment')
        for col in self.report_tree["columns"]:
            self.report_tree.heading(col, text=col)
            self.report_tree.column(col, width=100 if col in ['Sport', 'Plan'] else 120)
            
        for row in data:
            self.report_tree.insert('', 'end', values=(
                row[0], row[1], row[2], row[3], row[4], row[5], 
                row[6], row[7] or 'Never'
            ))
            
        summary = f"Expired Members: {len(data)}"
        self.summary_label.config(text=summary)
        self.current_report_data = {
            'type': 'Expired Members',
            'month': month,
            'data': data,
            'summary': summary
        }

    def export_report(self, format_type):
        if not hasattr(self, 'current_report_data'):
            messagebox.showwarning("Warning", "Generate a report first")
            return
            
        report_type = self.current_report_data['type']
        month = self.current_report_data['month']
        data = self.current_report_data['data']
        sport = self.current_report_data.get('sport')
        
        reports_dir = 'reports'
        os.makedirs(reports_dir, exist_ok=True)
        
        default_filename = f"{report_type.replace(' ', '')}_{month}"
        if sport and sport != "All":
            default_filename += f"_{sport}"
        default_filename = default_filename.replace(' ', '')
        
        if format_type == 'pdf':
            filename = filedialog.asksaveasfilename(
                initialdir=reports_dir,
                initialfile=f"{default_filename}.pdf",
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf")]
            )
        elif format_type == 'xlsx':
            filename = filedialog.asksaveasfilename(
                initialdir=reports_dir,
                initialfile=f"{default_filename}.xlsx",
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")]
            )
        else:
            filename = filedialog.asksaveasfilename(
                initialdir=reports_dir,
                initialfile=f"{default_filename}.csv",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")]
            )
            
        if not filename:
            return
            
        try:
            if report_type == "Expired Members":
                self.export_expired_report(format_type, filename, data, month)
            else:
                self.export_payment_report(format_type, filename, data, report_type, month, sport)
            messagebox.showinfo("Success", f"Report exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {str(e)}")
            logging.error(f"Export {format_type} failed: {str(e)}")

    def export_payment_report(self, format_type, filename, data, report_type, month, sport):
        headers = ['User ID', 'Name', 'CNIC', 'Contact', 'Sport', 'Plan', 'Amount', 'Date', 'Period', 'Treadmill']
        if report_type == "Sport Category":
            headers.insert(0, 'Sport')
            rows = [(row[5], row[1], row[2], row[3], row[4], row[6], f"Rs {row[7]:.2f}", row[8], 
                     row[9] or 'Full Month', 'Yes' if row[10] else 'No') for row in data]
        else:
            rows = [(row[1], row[2], row[3], row[4], row[5], row[6], f"Rs {row[7]:.2f}", row[8], 
                     row[9] or 'Full Month', 'Yes' if row[10] else 'No') for row in data]
        
        if format_type == 'pdf':
            doc = SimpleDocTemplate(filename, pagesize=letter)
            elements = []
            styles = getSampleStyleSheet()
            elements.append(Paragraph(f"{report_type} Report - {month}" + 
                                   (f" ({sport})" if sport and sport != "All" else ""), 
                                   styles['Title']))
            elements.append(Paragraph(self.current_report_data['summary'].replace('Rs ', 'Rs '), styles['Normal']))
            
            table_data = [headers] + rows
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(table)
            doc.build(elements)
            
        elif format_type == 'xlsx':
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = report_type.replace(' ', '')
            ws.append(headers)
            for row in rows:
                ws.append(row)
            wb.save(filename)
            
        else:  # csv
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)

    def export_expired_report(self, format_type, filename, data, month):
        headers = ['User ID', 'Name', 'CNIC', 'Contact', 'Sport', 'Plan', 'Expiry Date', 'Last Payment']
        rows = [(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7] or 'Never') 
                for row in data]
        
        if format_type == 'pdf':
            doc = SimpleDocTemplate(filename, pagesize=letter)
            elements = []
            styles = getSampleStyleSheet()
            elements.append(Paragraph(f"Expired Members Report - {month}", styles['Title']))
            elements.append(Paragraph(self.current_report_data['summary'], styles['Normal']))
            
            table_data = [headers] + rows
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(table)
            doc.build(elements)
            
        elif format_type == 'xlsx':
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "ExpiredMembers"
            ws.append(headers)
            for row in rows:
                ws.append(row)
            wb.save(filename)
            
        else:  # csv
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)

    def validate_date(self, date_str):
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    def validate_cnic(self, cnic):
        return bool(re.match(r'^\d{13}$', cnic))

    def validate_contact(self, contact):
        return bool(re.match(r'^\d{10,15}$', contact))

    def validate_user_id(self, user_id):
        return bool(re.match(r'^\d+$', user_id))

    def save_member(self):
        try:
            data = {k: v.get().strip() for k, v in self.member_entries.items()}
            required = ['user_id', 'name', 'contact', 'cnic', 'join_date', 'base_fee', 'expiry_date']
            if not all(data[field] for field in required):
                messagebox.showwarning("Warning", "Please fill all required fields")
                return
            
            if not self.validate_user_id(data['user_id']):
                messagebox.showwarning("Warning", "User ID must be numeric")
                return
                
            if not self.validate_cnic(data['cnic']):
                messagebox.showwarning("Warning", "CNIC must be 13 digits")
                return
                
            if not self.validate_contact(data['contact']):
                messagebox.showwarning("Warning", "Contact must be 10-15 digits")
                return
                
            if not self.validate_date(data['join_date']) or not self.validate_date(data['expiry_date']):
                messagebox.showwarning("Warning", "Dates must be in YYYY-MM-DD format")
                return
                
            sport = self.sport_var.get()
            if not sport:
                messagebox.showwarning("Warning", "Please select a sport category")
                return
                
            membership = self.membership_var.get()
            if not membership:
                messagebox.showwarning("Warning", "Please select a membership type")
                return
                
            try:
                base_fee = float(data['base_fee'])
                if base_fee <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("Warning", "Base Fee must be a positive number")
                return
                
            total_fee = base_fee + (400 if self.treadmill_var.get() else 0)
            
            photo_path = None
            if hasattr(self, 'photo_path') and self.photo_path:
                photos_dir = 'photos'
                os.makedirs(photos_dir, exist_ok=True)
                ext = os.path.splitext(self.photo_path)[1].lower()
                if ext not in ['.jpg', '.png']:
                    messagebox.showwarning("Warning", "Only JPG or PNG files allowed")
                    return
                photo_path = os.path.join(photos_dir, f"member_{data['user_id']}{ext}")
                Image.open(self.photo_path).save(photo_path)
            
            self.cursor.execute('''
                INSERT INTO members (
                    user_id, name, contact, cnic, location, designation, 
                    join_date, expiry_date, sport_category, membership_type, 
                    has_treadmill, base_fee, total_fee, is_active, updated_at, photo_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['user_id'], data['name'], data['contact'], data['cnic'], 
                data['location'] or None, data['designation'] or None,
                data['join_date'], data['expiry_date'], sport, 
                membership, self.treadmill_var.get(), 
                base_fee, total_fee, 1, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                photo_path
            ))
            self.conn.commit()
            messagebox.showinfo("Success", "Member registered successfully!")
            self.load_members()
            self.load_view_tab()
            self.clear_member_form()
            
        except sqlite3.IntegrityError as e:
            messagebox.showerror("Error", f"User ID or CNIC already exists: {str(e)}")
            logging.error(f"Save member failed: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"Registration failed: {str(e)}")
            logging.error(f"Save member failed: {str(e)}")

    def update_member(self):
        selected = self.members_tree.focus()
        if not selected:
            messagebox.showwarning("Warning", "No member selected")
            return
            
        try:
            old_user_id = self.members_tree.item(selected)['values'][1]  # User ID
            data = {k: v.get().strip() for k, v in self.member_entries.items()}
            
            required = ['user_id', 'name', 'contact', 'cnic', 'join_date', 'base_fee', 'expiry_date']
            if not all(data[field] for field in required):
                messagebox.showwarning("Warning", "Please fill all required fields")
                return
                
            if not self.validate_user_id(data['user_id']):
                messagebox.showwarning("Warning", "User ID must be numeric")
                return
                
            if not self.validate_cnic(data['cnic']):
                messagebox.showwarning("Warning", "CNIC must be 13 digits")
                return
                
            if not self.validate_contact(data['contact']):
                messagebox.showwarning("Warning", "Contact must be 10-15 digits")
                return
                
            if not self.validate_date(data['join_date']) or not self.validate_date(data['expiry_date']):
                messagebox.showwarning("Warning", "Dates must be in YYYY-MM-DD format")
                return
                
            sport = self.sport_var.get()
            if not sport:
                messagebox.showwarning("Warning", "Please select a sport category")
                return
                
            membership = self.membership_var.get()
            if not membership:
                messagebox.showwarning("Warning", "Please select a membership type")
                return
                
            try:
                base_fee = float(data['base_fee'])
                if base_fee <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("Warning", "Base Fee must be a positive number")
                return
                
            total_fee = base_fee + (400 if self.treadmill_var.get() else 0)
            
            photo_path = None
            self.cursor.execute("SELECT photo_path FROM members WHERE user_id=?", (old_user_id,))
            old_photo = self.cursor.fetchone()[0]
            if hasattr(self, 'photo_path') and self.photo_path:
                photos_dir = 'photos'
                os.makedirs(photos_dir, exist_ok=True)
                ext = os.path.splitext(self.photo_path)[1].lower()
                if ext not in ['.jpg', '.png']:
                    messagebox.showwarning("Warning", "Only JPG or PNG files allowed")
                    return
                photo_path = os.path.join(photos_dir, f"member_{data['user_id']}{ext}")
                Image.open(self.photo_path).save(photo_path)
                if old_photo and os.path.exists(old_photo):
                    try:
                        os.remove(old_photo)
                    except:
                        logging.warning(f"Failed to delete old photo: {old_photo}")
            else:
                photo_path = old_photo
            
            self.cursor.execute('''
                UPDATE members SET
                    user_id=?, name=?, contact=?, cnic=?, location=?, designation=?,
                    join_date=?, expiry_date=?, sport_category=?, membership_type=?,
                    has_treadmill=?, base_fee=?, total_fee=?, updated_at=?, photo_path=?
                WHERE user_id=? AND is_active=1
            ''', (
                data['user_id'], data['name'], data['contact'], data['cnic'], 
                data['location'] or None, data['designation'] or None,
                data['join_date'], data['expiry_date'], sport, 
                membership, self.treadmill_var.get(), 
                base_fee, total_fee, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                photo_path, old_user_id
            ))
            self.conn.commit()
            messagebox.showinfo("Success", "Member updated successfully!")
            self.load_members()
            self.load_view_tab()
            self.clear_member_form()
            
        except sqlite3.IntegrityError as e:
            messagebox.showerror("Error", f"User ID or CNIC already exists: {str(e)}")
            logging.error(f"Update member failed: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"Update failed: {str(e)}")
            logging.error(f"Update member failed: {str(e)}")

    def delete_member(self):
        selected = self.members_tree.focus()
        if not selected:
            messagebox.showwarning("Warning", "No member selected")
            return
            
        user_id = self.members_tree.item(selected)['values'][1]
        
        if messagebox.askyesno("Confirm", "Mark this member as inactive and delete photo?"):
            try:
                self.cursor.execute("SELECT photo_path FROM members WHERE user_id=?", (user_id,))
                photo_path = self.cursor.fetchone()[0]
                if photo_path and os.path.exists(photo_path):
                    try:
                        os.remove(photo_path)
                    except:
                        logging.warning(f"Failed to delete photo: {photo_path}")
                
                self.cursor.execute("UPDATE members SET is_active=0, updated_at=? WHERE user_id=?", 
                                  (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
                self.conn.commit()
                
                messagebox.showinfo("Success", "Member marked as inactive")
                self.load_members()
                self.load_view_tab()
                self.clear_member_form()
                
            except Exception as e:
                messagebox.showerror("Error", f"Delete failed: {str(e)}")
                logging.error(f"Delete member failed: {str(e)}")

    def delete_from_search(self):
        selected = self.search_results.focus()
        if not selected:
            messagebox.showwarning("Warning", "No member selected")
            return
            
        user_id = self.search_results.item(selected)['values'][0]
        
        if messagebox.askyesno("Confirm", "Mark this member as inactive and delete photo?"):
            try:
                self.cursor.execute("SELECT photo_path FROM members WHERE user_id=?", (user_id,))
                photo_path = self.cursor.fetchone()[0]
                if photo_path and os.path.exists(photo_path):
                    try:
                        os.remove(photo_path)
                    except:
                        logging.warning(f"Failed to delete photo: {photo_path}")
                
                self.cursor.execute("UPDATE members SET is_active=0, updated_at=? WHERE user_id=?", 
                                  (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
                self.conn.commit()
                messagebox.showinfo("Success", "Member marked as inactive")
                self.search_members()
                self.load_members()
                self.load_view_tab()
                
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Delete failed: {str(e)}")
                logging.error(f"Delete from search failed: {str(e)}")

    def clear_member_form(self):
        for entry in self.member_entries.values():
            entry.delete(0, 'end')
        self.sport_var.set("Gym")
        self.membership_var.set("30-day")
        self.treadmill_var.set(False)
        self.photo_label.config(text="No photo selected")
        if hasattr(self, 'photo_path'):
            delattr(self, 'photo_path')

    def search_members(self):
        search_value = self.search_member_entry.get().strip()
        if not search_value:
            messagebox.showwarning("Warning", "Please enter User ID or CNIC")
            return
            
        try:
            for row in self.search_results.get_children():
                self.search_results.delete(row)
                
            if re.match(r'^\d+$', search_value):
                self.cursor.execute('''
                    SELECT user_id, name, cnic, membership_type 
                    FROM members 
                    WHERE user_id=? AND is_active=1
                ''', (search_value,))
            else:
                self.cursor.execute('''
                    SELECT user_id, name, cnic, membership_type 
                    FROM members 
                    WHERE cnic=? AND is_active=1
                ''', (search_value,))
                
            members = self.cursor.fetchall()
            if members:
                for member in members:
                    self.search_results.insert('', 'end', values=member)
            else:
                messagebox.showinfo("Not Found", "No active member found")
                
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Search failed: {str(e)}")
            logging.error(f"Search members failed: {str(e)}")

    def view_search_result(self):
        selected = self.search_results.focus()
        if not selected:
            messagebox.showwarning("Warning", "No member selected")
            return
            
        user_id = self.search_results.item(selected)['values'][0]
        
        try:
            self.cursor.execute('''
                SELECT user_id, name, contact, cnic, location, designation, 
                       join_date, expiry_date, sport_category, membership_type, 
                       has_treadmill, base_fee, total_fee, photo_path 
                FROM members 
                WHERE user_id=? AND is_active=1
            ''', (user_id,))
            member = self.cursor.fetchone()
            
            if member:
                view_window = tk.Toplevel(self.root)
                view_window.title("Member Details")
                view_window.geometry("400x400")
                
                frame = ttk.Frame(view_window)
                frame.pack(fill='both', expand=True, padx=10, pady=10)
                
                info = f"""User ID: {member[0]}
Name: {member[1]}
Contact: {member[2]}
CNIC: {member[3]}
Location: {member[4] or 'N/A'}
Designation: {member[5] or 'N/A'}
Join Date: {member[6]}
Expiry Date: {member[7]}
Sport: {member[8]}
Membership Type: {member[9]}
Treadmill: {'Yes (+400)' if member[10] else 'No'}
Base Fee: Rs {member[11]:.2f}
Total Fee: Rs {member[12]:.2f}"""
                
                text = tk.Text(frame, height=12, width=30, wrap='word')
                text.insert('end', info)
                text.config(state='disabled')
                text.pack(side='left', padx=5)
                
                if member[13] and os.path.exists(member[13]):
                    try:
                        img = Image.open(member[13])
                        img = img.resize((100, 100), Image.LANCZOS)
                        photo = ImageTk.PhotoImage(img)
                        label = ttk.Label(frame, image=photo)
                        label.image = photo  # Keep reference
                        label.pack(side='right', padx=5)
                    except Exception as e:
                        logging.error(f"Failed to display photo in view: {str(e)}")
                
                ttk.Button(frame, text="Close", command=view_window.destroy).pack(pady=10)
            else:
                messagebox.showerror("Error", "Member not found")
                
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"View failed: {str(e)}")
            logging.error(f"View search result failed: {str(e)}")

    def load_for_update(self):
        selected = self.search_results.focus()
        if not selected:
            messagebox.showwarning("Warning", "No member selected")
            return
            
        user_id = self.search_results.item(selected)['values'][0]
        
        try:
            self.cursor.execute('''
                SELECT user_id, name, contact, cnic, location, designation, 
                       join_date, expiry_date, sport_category, membership_type, 
                       has_treadmill, base_fee, total_fee, photo_path 
                FROM members 
                WHERE user_id=? AND is_active=1
            ''', (user_id,))
            member = self.cursor.fetchone()
            
            if member:
                self.clear_member_form()
                self.member_entries['user_id'].insert(0, member[0])
                self.member_entries['name'].insert(0, member[1])
                self.member_entries['contact'].insert(0, member[2])
                self.member_entries['cnic'].insert(0, member[3])
                self.member_entries['location'].insert(0, member[4] if member[4] else '')
                self.member_entries['designation'].insert(0, member[5] if member[5] else '')
                self.member_entries['join_date'].insert(0, member[6])
                self.member_entries['expiry_date'].insert(0, member[7])
                self.sport_var.set(member[8])
                self.membership_var.set(member[9])
                self.treadmill_var.set(member[10])
                self.member_entries['base_fee'].insert(0, member[11])
                self.photo_label.config(text=os.path.basename(member[13]) if member[13] else "No photo selected")
                if member[13]:
                    self.photo_path = member[13]
            else:
                messagebox.showerror("Error", "Member not found")
                
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Load for update failed: {str(e)}")
            logging.error(f"Load for update failed: {str(e)}")

    def redirect_to_payment(self):
        selected = self.search_results.focus()
        if not selected:
            messagebox.showwarning("Warning", "No member selected")
            return
            
        user_id = self.search_results.item(selected)['values'][0]
        
        try:
            self.cursor.execute("SELECT cnic FROM members WHERE user_id=? AND is_active=1", (user_id,))
            cnic = self.cursor.fetchone()
            if cnic:
                self.notebook.select(self.payment_frame)
                self.search_entry.delete(0, 'end')
                self.search_entry.insert(0, cnic[0])
                self.search_member()
            else:
                messagebox.showerror("Error", "Member not found")
                
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Redirect to payment failed: {str(e)}")
            logging.error(f"Redirect to payment failed: {str(e)}")

    def load_members(self):
        for row in self.members_tree.get_children():
            self.members_tree.delete(row)
        
        try:
            self.cursor.execute('''
                SELECT user_id, name, contact, cnic, location, designation, 
                       join_date, expiry_date, sport_category, membership_type, 
                       has_treadmill, base_fee, total_fee 
                FROM members 
                WHERE is_active=1 
                ORDER BY user_id
            ''')
        
            members = self.cursor.fetchall()
            for i, member in enumerate(members, 1):
                self.members_tree.insert('', 'end', values=(
                    i, member[0], member[1], member[2], member[3], member[4] or '', member[5] or '',
                    member[6], member[7], member[8], member[9], 
                    'Yes' if member[10] else 'No', f"Rs {member[11]:.2f}", f"Rs {member[12]:.2f}"
                ))
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load members: {str(e)}")
            logging.error(f"Load members failed: {str(e)}")

    def load_view_tab(self):
        for row in self.view_tree.get_children():
            self.view_tree.delete(row)
            
        try:
            self.cursor.execute('''
                SELECT user_id, name, contact, sport_category, membership_type, has_treadmill, 
                       base_fee, total_fee 
                FROM members 
                WHERE is_active=1 
                ORDER BY user_id
            ''')
            
            members = self.cursor.fetchall()
            for i, member in enumerate(members, 1):
                self.cursor.execute('''
                    SELECT payment_date 
                    FROM payments 
                    WHERE user_id=? 
                    ORDER BY payment_date DESC 
                    LIMIT 1
                ''', (member[0],))
                last_payment = self.cursor.fetchone()
                
                self.view_tree.insert('', 'end', values=(
                    i, member[0], member[1], member[2], member[3], member[4], 
                    'Yes' if member[5] else 'No', f"Rs {member[6]:.2f}", f"Rs {member[7]:.2f}",
                    last_payment[0] if last_payment else "Never"
                ))
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load view tab: {str(e)}")
            logging.error(f"Load view tab failed: {str(e)}")

    def load_selected_member(self, event):
        selected = self.members_tree.focus()
        if selected:
            member = self.members_tree.item(selected)['values']
            self.clear_member_form()
            
            self.member_entries['user_id'].insert(0, member[1])
            self.member_entries['name'].insert(0, member[2])
            self.member_entries['contact'].insert(0, member[3])
            self.member_entries['cnic'].insert(0, member[4])
            self.member_entries['location'].insert(0, member[5])
            self.member_entries['designation'].insert(0, member[6])
            self.member_entries['join_date'].insert(0, member[7])
            self.member_entries['expiry_date'].insert(0, member[8])
            self.sport_var.set(member[9])
            self.membership_var.set(member[10])
            self.treadmill_var.set(True if member[11] == 'Yes' else False)
            self.member_entries['base_fee'].insert(0, float(member[12].replace('Rs ', '')))
            
            self.cursor.execute("SELECT photo_path FROM members WHERE user_id=?", (member[1],))
            photo_path = self.cursor.fetchone()[0]
            self.photo_label.config(text=os.path.basename(photo_path) if photo_path else "No photo selected")
            if photo_path:
                self.photo_path = photo_path

    def search_member(self):
        search_value = self.search_entry.get().strip()
        if not search_value:
            messagebox.showwarning("Warning", "Please enter search value")
            return
            
        try:
            self.cursor.execute('''
                SELECT user_id, name, contact, cnic, location, designation, 
                       join_date, expiry_date, sport_category, membership_type, 
                       has_treadmill, base_fee, total_fee, photo_path 
                FROM members 
                WHERE (user_id=? OR cnic=?) AND is_active=1
            ''', (search_value, search_value))
                
            member = self.cursor.fetchone()
            
            if member:
                self.current_member = member
                self.display_member_info(member)
                self.load_payment_history(member[0])
                self.amount_entry.delete(0, 'end')
                self.amount_entry.insert(0, str(member[12]))
                self.payment_membership_var.set(member[9])
            else:
                messagebox.showinfo("Not Found", "No active member found")
                self.member_info.config(state='normal')
                self.member_info.delete('1.0', 'end')
                self.member_info.config(state='disabled')
                for row in self.payment_history.get_children():
                    self.payment_history.delete(row)
                
        except Exception as e:
            messagebox.showerror("Error", f"Search failed: {str(e)}")
            logging.error(f"Search member failed: {str(e)}")

    def display_member_info(self, member):
        self.member_info.config(state='normal')
        self.member_info.delete('1.0', 'end')
        
        info = f"""User ID: {member[0]}
Name: {member[1]}
Contact: {member[2]}
CNIC: {member[3]}
Location: {member[4] or 'N/A'}
Designation: {member[5] or 'N/A'}
Join Date: {member[6]}
Expiry Date: {member[7]}
Sport: {member[8]}
Membership Type: {member[9]}
Treadmill: {'Yes (+400)' if member[10] else 'No'}
Base Fee: Rs {member[11]:.2f}
Total Fee: Rs {member[12]:.2f}"""
        
        self.member_info.insert('end', info)
        self.member_info.config(state='disabled')

    def load_payment_history(self, user_id):
        for row in self.payment_history.get_children():
            self.payment_history.delete(row)
            
        try:
            self.cursor.execute('''
                SELECT id, payment_date, amount, month, period 
                FROM payments 
                WHERE user_id=? 
                ORDER BY payment_date DESC
            ''', (user_id,))
            for payment in self.cursor.fetchall():
                period = payment[4] or 'Full Month'
                self.payment_history.insert('', 'end', values=(
                    payment[0], payment[1], f"Rs {payment[2]:.2f}", payment[3], period
                ))
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load payment history: {str(e)}")
            logging.error(f"Load payment history failed: {str(e)}")

    def record_payment(self):
        if not hasattr(self, 'current_member'):
            messagebox.showwarning("Warning", "No member selected")
            return
            
        try:
            amount = float(self.amount_entry.get())
            month = self.month_entry.get().strip()
            membership_type = self.payment_membership_var.get()
            
            if amount <= 0:
                messagebox.showwarning("Warning", "Amount must be positive")
                return
                
            if not re.match(r'^\d{4}-\d{2}$', month):
                messagebox.showwarning("Warning", "Month must be in YYYY-MM format")
                return
                
            if not membership_type:
                messagebox.showwarning("Warning", "Please select a membership type")
                return
                
            if amount != self.current_member[12]:
                messagebox.showwarning("Warning", f"Amount must be Rs {self.current_member[12]:.2f} (Total Fee)")
                return
                
            if membership_type != self.current_member[9]:
                self.cursor.execute('''
                    UPDATE members 
                    SET membership_type=?, updated_at=? 
                    WHERE user_id=?
                ''', (
                    membership_type, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                    self.current_member[0]
                ))
            
            period = None
            if membership_type == '15-day':
                self.cursor.execute('''
                    SELECT period 
                    FROM payments 
                    WHERE user_id=? AND month=?
                ''', (self.current_member[0], month))
                existing_periods = [row[0] for row in self.cursor.fetchall()]
                
                if 'first_half' not in existing_periods:
                    period = 'first_half'
                elif 'second_half' not in existing_periods:
                    period = 'second_half'
                else:
                    messagebox.showerror("Error", "Two 15-day payments already recorded for this month")
                    return
            
            self.cursor.execute('''
                INSERT INTO payments (user_id, amount, payment_date, month, period, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                self.current_member[0], amount, datetime.now().strftime("%Y-%m-%d"),
                month, period, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
            self.conn.commit()
            messagebox.showinfo("Success", f"Payment of Rs {amount:.2f} recorded for {month} ({period or 'Full Month'})!")
            self.load_payment_history(self.current_member[0])
            self.load_view_tab()
            self.search_entry.delete(0, 'end')
            self.member_info.config(state='normal')
            self.member_info.delete('1.0', 'end')
            self.member_info.config(state='disabled')
            for row in self.payment_history.get_children():
                self.payment_history.delete(row)
            self.amount_entry.delete(0, 'end')
            self.month_entry.delete(0, 'end')
            self.month_entry.insert(0, (datetime.now() + timedelta(days=30)).strftime("%Y-%m"))
            self.payment_membership_var.set('')
            delattr(self, 'current_member')
            
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Payment already recorded for this period")
            logging.error(f"Payment failed: Duplicate payment for member {self.current_member[0]}, month {month}, period {period}")
        except ValueError:
            messagebox.showerror("Error", "Invalid amount")
            logging.error(f"Payment failed: Invalid amount for member {self.current_member[0]}")
        except Exception as e:
            messagebox.showerror("Error", f"Payment failed: {str(e)}")
            logging.error(f"Payment failed: {str(e)}")

    def __del__(self):
        try:
            self.conn.close()
        except:
            pass

if __name__ == "__main__":
    root = tk.Tk()
    app = GymManagementSystem(root)
    root.mainloop()