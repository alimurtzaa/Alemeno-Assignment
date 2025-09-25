from django.urls import path
from .views import RegisterAPIView, CheckEligibilityAPIView, LoanDetailAPIView, CustomerLoansAPIView, CreateLoanAPIView

urlpatterns = [
    path("register/", RegisterAPIView.as_view(), name="register"),
    path("check-eligibility/", CheckEligibilityAPIView.as_view(), name="check_elig"),
    path("view-loan/<int:loan_id>/", LoanDetailAPIView.as_view(), name="view_loan"),
    path("view-loans/<int:customer_id>/", CustomerLoansAPIView.as_view(), name="view_loans_customer"),
    path('create-loan/', CreateLoanAPIView.as_view(), name='create-loan'),

]
