from rest_framework import serializers
from .models import Customer, Loan

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'first_name', 'last_name', 'age', 'phone_number', 'monthly_salary', 'approved_limit']


class LoanSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer(read_only=True)
    class Meta:
        model = Loan
        fields = ['id', 'external_loan_id', 'customer', 'loan_amount', 'tenure', 'interest_rate', 'monthly_payment', 'repayments_left', 'loan_approved']
