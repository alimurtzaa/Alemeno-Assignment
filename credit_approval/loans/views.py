from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Customer, Loan
from .serializers import CustomerSerializer, LoanSerializer
from decimal import Decimal
from math import pow
from datetime import date, datetime
from django.db.models import Sum
from dateutil.relativedelta import relativedelta



def round_to_nearest_lakh(x):
    lakh = 100000
    return int(round(x / lakh)) * lakh

def compute_emi(P: Decimal, annual_rate: Decimal, n_months: int) -> Decimal:
    if n_months == 0:
        return Decimal(0)
    r = float(annual_rate) / 12 / 100  # monthly rate as float for pow
    if r == 0:
        return Decimal(P / n_months)
    emi = float(P) * r * pow((1 + r), n_months) / (pow((1 + r), n_months) - 1)
    return Decimal(emi).quantize(Decimal("0.01"))


class RegisterAPIView(APIView):
    def post(self, request):
        data = request.data
        monthly_income = int(data.get("monthly_income") or data.get("monthly_salary") or 0)
        approved_limit = round_to_nearest_lakh(36 * monthly_income)
        customer = Customer.objects.create(
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            age=int(data.get("age") or 0),
            phone_number=str(data.get("phone_number") or ""),
            monthly_salary=monthly_income,
            approved_limit=approved_limit,
        )
        resp = {
            "customer_id": customer.id,
            "name": f"{customer.first_name} {customer.last_name}",
            "age": customer.age,
            "monthly_income": customer.monthly_salary,
            "approved_limit": customer.approved_limit,
            "phone_number": customer.phone_number,
        }
        return Response(resp, status=status.HTTP_201_CREATED)


# Helper to compute credit score
def compute_credit_score(customer: Customer) -> int:
    loans = Loan.objects.filter(customer=customer)
    # Sum of current active loans (end_date >= today or loan_approved)
    today = date.today()
    active_loans = loans.filter(end_date__gte=today) | loans.filter(loan_approved=True)
    sum_current = active_loans.aggregate(total=Sum('loan_amount'))['total'] or 0
    if sum_current > customer.approved_limit:
        return 0

    # i) Past loans paid on time: compute average on-time ratio
    ratios = []
    for l in loans:
        if l.tenure and l.tenure > 0:
            ratios.append(min(1.0, float(l.emis_paid_on_time) / float(l.tenure)))
    avg_on_time = sum(ratios) / len(ratios) if ratios else 1.0

    # ii) Number of loans taken - penalize many loans
    num_loans = loans.count()
    loans_score = max(0.0, 1 - (num_loans / 10.0))  # 10 loans or more => 0

    # iii) activity in current year
    this_year = today.year
    activity = loans.filter(start_date__year=this_year).count()
    activity_score = min(1.0, activity / 3.0)

    # iv) approved volume (sum of loans / approved_limit)
    approved_volume = loans.aggregate(total=Sum('loan_amount'))['total'] or 0
    if customer.approved_limit:
        vol_score = max(0.0, 1 - float(approved_volume) / float(customer.approved_limit))
    else:
        vol_score = 0.0

    # weighted sum (weights chosen sensibly)
    score = 100 * (0.5 * avg_on_time + 0.2 * loans_score + 0.15 * activity_score + 0.15 * vol_score)
    score = int(max(0, min(100, round(score))))
    return score


class CheckEligibilityAPIView(APIView):
    def post(self, request):
        data = request.data
        cust_id = data.get("customer_id")
        customer = get_object_or_404(Customer, id=cust_id)
        loan_amount = Decimal(str(data.get("loan_amount", 0)))
        interest_rate = Decimal(str(data.get("interest_rate", 0)))
        tenure = int(data.get("tenure", 0))
        # compute score
        score = compute_credit_score(customer)

        approved = False
        message = ""
        if score > 50:
            approved = True
        elif 30 < score <= 50:
            # per spec: approve loans with interest rate > 12%
            if float(interest_rate) > 12.0:
                approved = True
            else:
                approved = False
        else:
            approved = False

        loan_id = None
        monthly_inst = None
        if approved:
            monthly_inst = compute_emi(loan_amount, interest_rate, tenure)
            # create loan record
            loan = Loan.objects.create(
                customer=customer,
                loan_amount=loan_amount,
                tenure=tenure,
                interest_rate=interest_rate,
                monthly_payment=monthly_inst,
                loan_approved=True,
                repayments_left=tenure,
            )
            loan_id = loan.id
            message = "Loan approved"
        else:
            message = "Loan not approved due to low credit score"

        resp = {
            "loan_id": loan_id,
            "customer_id": customer.id,
            "loan_approved": approved,
            "interest_rate": float(interest_rate),
            "message": message,
            "credit_score": score,
            "monthly_installment": float(monthly_inst) if monthly_inst else None,
        }
        return Response(resp, status=status.HTTP_200_OK)

class CreateLoanAPIView(APIView):
    def post(self, request):
        data = request.data
        cust_id = data.get("customer_id")
        
        customer = get_object_or_404(Customer, id=cust_id)
        
        loan_amount = Decimal(str(data.get("loan_amount", 0)))
        interest_rate = Decimal(str(data.get("interest_rate", 0)))
        tenure = int(data.get("tenure", 0))
        
        if loan_amount <= 0:
            return Response({
                "loan_id": None,
                "customer_id": customer.id,
                "loan_approved": False,
                "message": "Loan amount must be greater than 0",
                "monthly_installment": 0.0
            }, status=status.HTTP_400_BAD_REQUEST)
            
        if interest_rate < 0:
            return Response({
                "loan_id": None,
                "customer_id": customer.id,
                "loan_approved": False,
                "message": "Interest rate cannot be negative",
                "monthly_installment": 0.0
            }, status=status.HTTP_400_BAD_REQUEST)
            
        if tenure <= 0:
            return Response({
                "loan_id": None,
                "customer_id": customer.id,
                "loan_approved": False,
                "message": "Tenure must be greater than 0 months",
                "monthly_installment": 0.0
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Compute credit score
        score = compute_credit_score(customer)
        
        approved = False
        corrected_interest_rate = interest_rate
        message = ""
        
        if score == 0:
            approved = False
            message = "Loan rejected: Sum of current loans exceeds approved credit limit"
        elif score > 50:
            # Approve loan at requested interest rate
            approved = True
            message = "Loan approved"
        elif 30 < score <= 50:
            # Approve loans with interest rate > 12%
            if float(interest_rate) > 12.0:
                approved = True
                message = "Loan approved"
            else:
                # Correct interest rate to minimum 12%
                corrected_interest_rate = Decimal("12.0")
                approved = True
                message = "Loan approved with corrected interest rate"
        elif 10 < score <= 30:
            # Approve loans with interest rate > 16%
            if float(interest_rate) > 16.0:
                approved = True
                message = "Loan approved"
            else:
                # Correct interest rate to minimum 16%
                corrected_interest_rate = Decimal("16.0")
                approved = True
                message = "Loan approved with corrected interest rate"
        else:  # score <= 10
            approved = False
            message = "Loan rejected: Credit score too low"
        
        if approved:
            today = date.today()
            active_loans = Loan.objects.filter(
                customer=customer, 
                loan_approved=True, 
                repayments_left__gt=0
            )
            current_emis = sum(float(loan.monthly_payment or 0) for loan in active_loans)
            
            proposed_emi = compute_emi(loan_amount, corrected_interest_rate, tenure)
            total_emis = current_emis + float(proposed_emi)
            
            max_emi_allowed = float(customer.monthly_salary) * 0.5
            
            if total_emis > max_emi_allowed:
                approved = False
                message = "Loan rejected: Total EMIs would exceed 50% of monthly salary"
        
        # Create loan if approved
        loan_id = None
        monthly_installment = 0.0
        
        if approved:
            monthly_installment = compute_emi(loan_amount, corrected_interest_rate, tenure)

            
            start_date = date.today()
            end_date = start_date + relativedelta(months=tenure)
            
            loan = Loan.objects.create(
                customer=customer,
                loan_amount=loan_amount,
                tenure=tenure,
                interest_rate=corrected_interest_rate,
                monthly_payment=monthly_installment,
                loan_approved=True,
                repayments_left=tenure,
                start_date=start_date,
                end_date=end_date,
                emis_paid_on_time=0
            )
            loan_id = loan.id
            
            customer.current_debt += loan_amount
            customer.save()
        
        resp = {
            "loan_id": loan_id,
            "customer_id": customer.id,
            "loan_approved": approved,
            "message": message,
            "monthly_installment": float(monthly_installment)
        }
        
        return Response(resp, status=status.HTTP_201_CREATED if approved else status.HTTP_200_OK)


class LoanDetailAPIView(APIView):
    def get(self, request, loan_id):
        loan = get_object_or_404(Loan, id=loan_id)
        serializer = LoanSerializer(loan)
        return Response(serializer.data)


class CustomerLoansAPIView(APIView):
    def get(self, request, customer_id):
        customer = get_object_or_404(Customer, id=customer_id)
        loans = Loan.objects.filter(customer=customer)
        # filter "current" loans: where repayments_left>0 or end_date in future
        from datetime import date
        today = date.today()
        current_loans = loans.filter(repayments_left__gt=0) | loans.filter(end_date__gte=today)
        serializer = LoanSerializer(current_loans.distinct(), many=True)
        return Response(serializer.data)
