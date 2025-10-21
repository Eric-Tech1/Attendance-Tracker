from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    path('', views.redirect_dashboard, name='attendance_home'),
    path('student-dashboard/', views.StudentDashboardView.as_view(), name='student_dashboard'),
    path('admin-dashboard/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
    path('my-records/', views.MyRecordsView.as_view(), name='my_records'),
    path('all-records/', views.AllRecordsView.as_view(), name='all_records'),
    path('check-in/', views.check_in, name='check_in'),
    path('check-out/', views.check_out, name='check_out'),
    path('export-csv/', views.export_csv, name='export_csv'),
    path("students/", views.StudentListView.as_view(), name="student_list"),
    path("students/add/", views.StudentCreateView.as_view(), name="student_add"),
    path("students/<int:pk>/edit/", views.StudentUpdateView.as_view(), name="student_edit"),
    path("students/<int:pk>/delete/", views.StudentDeleteView.as_view(), name="student_delete"),
    path("locations/", views.LocationListView.as_view(), name="location_list"),
    path("reports/", views.ReportView.as_view(), name="reports"),
    path('locations/<int:pk>/edit/', views.LocationUpdateView.as_view(), name='location_edit'),
    path("records/", views.AdminRecordsView.as_view(), name="admin_records"),
    path("fingerprint/register/", views.register_fingerprint_page, name="register_fingerprint_page"),
    path('webauthn/register/begin/', views.webauthn_register_begin, name='webauthn_register_begin'),
    path('webauthn/register/complete/', views.webauthn_register_complete, name='webauthn_register_complete'),
    path('webauthn/authenticate/complete/', views.webauthn_authenticate_complete, name='webauthn_authenticate_complete'),
    path('webauthn/authenticate/complete/', views.webauthn_authenticate_complete, name='webauthn_authenticate_complete'),

]