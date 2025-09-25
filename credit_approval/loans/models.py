from django.db import models

class Customer(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    age = models.IntegerField()
    phone_number = models.CharField(max_length=20)
    monthly_salary = models.BigIntegerField()
    approved_limit = models.BigIntegerField(default=0)
    current_debt = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} (id={self.id})"


class Loan(models.Model):
    customer = models.ForeignKey(Customer, related_name='loans', on_delete=models.CASCADE)
    external_loan_id = models.CharField(max_length=50, null=True, blank=True)  # original Loan ID from excel
    loan_amount = models.DecimalField(max_digits=14, decimal_places=2)
    tenure = models.IntegerField(help_text="Tenure in months")
    interest_rate = models.DecimalField(max_digits=6, decimal_places=2)  # annual %
    monthly_payment = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    emis_paid_on_time = models.IntegerField(default=0)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    loan_approved = models.BooleanField(default=False)
    repayments_left = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Loan {self.pk} for {self.customer}"
