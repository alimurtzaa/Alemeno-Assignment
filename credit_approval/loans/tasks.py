from celery import shared_task
import os
import pandas as pd
from django.conf import settings
from .models import Customer, Loan
from decimal import Decimal
from datetime import datetime

@shared_task
def ingest_excel_data():
    base = getattr(settings, "BASE_DIR")
    data_dir = os.path.join(base, "data")
    cust_file = os.path.join(data_dir, "customer_data.xlsx")
    loan_file = os.path.join(data_dir, "loan_data.xlsx")

    # Customers
    if os.path.exists(cust_file):
        df_cust = pd.read_excel(cust_file, engine="openpyxl")
        for _, r in df_cust.iterrows():
            # If you want to preserve original Customer ID, you can assign it to a field;
            # here we match by phone_number to avoid duplicates
            phone = str(r.get("Phone Number") or r.get("phone_number") or "")
            monthly_salary = int(r.get("Monthly Salary") or 0)
            approved_limit = int(round(monthly_salary * 36 / 100000.0)) * 100000
            obj, created = Customer.objects.update_or_create(
                phone_number=phone,
                defaults={
                    "first_name": r.get("First Name") or r.get("first_name"),
                    "last_name": r.get("Last Name") or r.get("last_name"),
                    "age": int(r.get("Age") or 0),
                    "monthly_salary": monthly_salary,
                    "approved_limit": approved_limit,
                },
            )

    # Loans
    if os.path.exists(loan_file):
        df_loan = pd.read_excel(loan_file, engine="openpyxl")
        for _, r in df_loan.iterrows():
            cust_id = r.get("Customer ID") or r.get("customer id") or r.get("customer_id")
            # find customer by id if you preserved it, else by phone / name
            try:
                # attempt by primary key if it matches
                customer = Customer.objects.filter(id=int(cust_id)).first()
            except Exception:
                customer = None
            if not customer:
                # fallback: try to skip if no matching customer
                continue
            loan_amount = Decimal(r.get("Loan Amount") or 0)
            tenure = int(r.get("Tenure") or 0)
            interest_rate = Decimal(r.get("Interest Rate") or 0)
            monthly_payment = Decimal(r.get("Monthly payment") or 0)
            emis_on_time = int(r.get("EMIs paid on Time") or 0)
            start_str = r.get("Date of Approval") or r.get("start date")
            end_str = r.get("End Date") or r.get("end date")
            def parse_date(x):
                if pd.isna(x): return None
                if isinstance(x, datetime): return x.date()
                try:
                    return pd.to_datetime(x).date()
                except Exception:
                    return None
            start_date = parse_date(start_str)
            end_date = parse_date(end_str)
            Loan.objects.update_or_create(
                external_loan_id=str(r.get("Loan ID") or ""),
                customer=customer,
                defaults={
                    "loan_amount": loan_amount,
                    "tenure": tenure,
                    "interest_rate": interest_rate,
                    "monthly_payment": monthly_payment,
                    "emis_paid_on_time": emis_on_time,
                    "start_date": start_date,
                    "end_date": end_date,
                    "loan_approved": True,  # existing loans from data are assumed approved
                    "repayments_left": max(0, tenure - emis_on_time),
                },
            )
    return "ingest done"
