from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from django.shortcuts import redirect, render, get_object_or_404
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
import csv
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView
from django.urls import reverse_lazy
from .models import Student, AttendanceRecord, Location
from .forms import DateRangeForm
from .utils import calculate_distance
from django.contrib.auth.mixins import  UserPassesTestMixin
from django.contrib.auth.models import User
from .forms import StudentForm

# ---------------- UTILS ----------------
def staff_or_admin(user):
    return user.is_staff or user.is_superuser


def redirect_dashboard(request):
    if request.user.is_staff:
        return redirect('attendance:admin_dashboard')   
    else:
        return redirect('attendance:student_dashboard') 


# ---------------- STUDENT ----------------
@method_decorator(login_required, name='dispatch')
class StudentDashboardView(TemplateView):
    template_name = 'attendance/student_dashboard.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_staff:
            return redirect('attendance:admin_dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        student = get_object_or_404(Student, user=self.request.user)
        today = timezone.localdate()
        ctx['today_record'] = AttendanceRecord.objects.filter(student=student, date=today).first()
        ctx['now'] = timezone.now()
        ctx['records'] = AttendanceRecord.objects.filter(student=student).order_by('-date')[:10]
        ctx['locations'] = Location.objects.all()
        return ctx


@login_required
def check_in(request):
    """Handle student check-in with GPS validation and duplicate prevention."""
    student = get_object_or_404(Student, user=request.user)

    if request.method == "POST":
        location_id = request.POST.get("location")
        user_lat = request.POST.get("latitude")
        user_lon = request.POST.get("longitude")

        # ✅ Step 1: Ensure form has all required data
        if not location_id or not user_lat or not user_lon:
            messages.error(request, "⚠️ Missing location or GPS data.")
            return redirect("attendance:student_dashboard")

        try:
            # ✅ Step 2: Get selected lab
            location = get_object_or_404(Location, id=location_id)

            # ✅ Step 3: Convert values
            user_lat, user_lon = float(user_lat), float(user_lon)
            loc_lat, loc_lon = float(location.latitude), float(location.longitude)
            allowed_radius = float(location.allowed_radius)

            # ✅ Step 4: Calculate distance
            distance = calculate_distance(user_lat, user_lon, loc_lat, loc_lon)
            print(f"📍 Distance from {location.name}: {distance:.2f}m (allowed: {allowed_radius}m)")

            if distance > allowed_radius:
                messages.error(request, f"❌ Too far from {location.name}. Move closer to check in.")
                return redirect("attendance:student_dashboard")

            # ✅ Step 5: Handle record
            today = timezone.localdate()
            record, created = AttendanceRecord.objects.get_or_create(
                student=student,
                date=today,
                defaults={
                    "check_in": timezone.now(),
                    "location": location,
                    "status": "Present",
                    "latitude": user_lat,
                    "longitude": user_lon,
                }
            )

            if not created:  # record already exists
                if record.check_in:
                    messages.info(request, f"ℹ️ Already checked in today at {record.location.name}.")
                else:
                    record.check_in = timezone.now()
                    record.location = location
                    record.status = "Present"
                    record.latitude = user_lat
                    record.longitude = user_lon
                    record.save()
                    messages.success(request, f"✅ Checked in successfully at {location.name}.")
            else:
                messages.success(request, f"✅ Checked in successfully at {location.name}.")

        except Exception as e:
            print("⚠️ Error during check_in:", e)
            messages.error(request, f"Unexpected error: {e}")

    return redirect("attendance:student_dashboard")




@login_required
def check_out(request):
    student = get_object_or_404(Student, user=request.user)
    today = timezone.localdate()
    record = AttendanceRecord.objects.filter(student=student, date=today).first()

    if not record or not record.check_in:
        messages.error(request, 'You have not checked in today.')
    elif record.check_out:
        messages.info(request, 'You already checked out today.')
    else:
        record.check_out = timezone.now()
        record.save()
        messages.success(request, 'Checked out successfully!')
    return redirect('attendance:student_dashboard')


@method_decorator(login_required, name='dispatch')
class MyRecordsView(ListView):
    model = AttendanceRecord
    template_name = 'attendance/my_records.html'
    context_object_name = 'records'
    paginate_by = 20

    def get_queryset(self):
        student = get_object_or_404(Student, user=self.request.user)
        return AttendanceRecord.objects.filter(student=student).order_by('-date')


# ---------------- ADMIN ----------------
@method_decorator([login_required, user_passes_test(staff_or_admin)], name='dispatch')
class AdminDashboardView(TemplateView):
    template_name = 'attendance/admin_dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()

        # Total students
        total_students = Student.objects.count()
        ctx['total_students'] = total_students

        # Total attendance records
        ctx['total_records'] = AttendanceRecord.objects.count()

        # Attendance today
        today_records = AttendanceRecord.objects.filter(date=today)
        present_today = today_records.filter(status="Present").count()
        absent_today = total_students - present_today if total_students else 0

        ctx['today_records'] = today_records
        ctx['present_today'] = present_today
        ctx['absent_today'] = absent_today
        ctx['today_records_count'] = today_records.count()

        # Recent 10 records (with student relation)
        ctx['recent_records'] = (
            AttendanceRecord.objects
            .select_related("student")
            .order_by("-date")[:10]
        )

        return ctx


@method_decorator([login_required, user_passes_test(staff_or_admin)], name='dispatch')
class AllRecordsView(ListView):
    model = AttendanceRecord
    template_name = 'attendance/all_records.html'
    context_object_name = 'records'
    paginate_by = 50

    def get_queryset(self):
        qs = AttendanceRecord.objects.select_related('student__user', 'location').order_by('-date', '-check_in')
        start = self.request.GET.get('start')
        end = self.request.GET.get('end')
        if start and end:
            qs = qs.filter(date__range=[start, end])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        ctx['form'] = DateRangeForm(self.request.GET or None)
        ctx['total'] = qs.count()
        ctx['present'] = qs.filter(status="Present").count()
        ctx['absent'] = qs.filter(status="Absent").count()
        return ctx


@login_required
@user_passes_test(staff_or_admin)
def export_csv(request):
    form = DateRangeForm(request.GET or None)
    if form.is_valid():
        start, end = form.cleaned_data['start'], form.cleaned_data['end']
        rows = AttendanceRecord.objects.filter(date__range=[start, end]).values_list(
            'student__user__username', 'date', 'check_in', 'check_out', 'status', 'location__name'
        )

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="attendance_{start}_{end}.csv"'

        writer = csv.writer(response)
        writer.writerow(['Username', 'Date', 'Check In', 'Check Out', 'Status', 'Location'])
        for row in rows:
            writer.writerow(row)
        return response

    messages.error(request, 'Invalid date range')
    return redirect('attendance:all_records')

class StudentListView(ListView):
    model = Student
    template_name = "attendance/student_list.html"
    context_object_name = "students"

class StudentCreateView(CreateView):
    model = Student
    fields = ["first_name", "last_name", "matric_no", "department"]
    template_name = "attendance/student_form.html"
    success_url = reverse_lazy("attendance:student_list")

    def form_valid(self, form):
        # Don’t commit yet, so we can attach the User
        student = form.save(commit=False)

        # Use matric_no as username
        username = form.cleaned_data["matric_no"]

        # Create the user with default password
        user = User.objects.create_user(
            username=username,
            password="password1",
            first_name=form.cleaned_data["first_name"],
            last_name=form.cleaned_data["last_name"]
        )

        # Link the user to the student record
        student.user = user
        student.save()

        print("✅ Student and user saved successfully")
        return super().form_valid(form)

    def form_invalid(self, form):
        print("❌ Form errors:", form.errors)
        return super().form_invalid(form)
    
class StudentUpdateView(UpdateView):
    model = Student
    fields = ["user", "matric_no", "department"]
    template_name = "attendance/student_form.html"
    success_url = reverse_lazy("attendance:student_list")

class StudentDeleteView(DeleteView):
    model = Student
    template_name = "attendance/student_confirm_delete.html"
    success_url = reverse_lazy("attendance:student_list")


# Reports
class ReportView(TemplateView):
    template_name = "attendance/reports.html"

class LocationListView(ListView):
    model = Location
    template_name = 'attendance/location_list.html'
    context_object_name = 'locations'


class LocationUpdateView(UpdateView):
    model = Location
    fields = ['name', 'latitude', 'longitude', 'allowed_radius']
    template_name = 'attendance/location_form.html'
    success_url = reverse_lazy('attendance:location_list')


class AdminRecordsView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = AttendanceRecord
    template_name = "attendance/admin_records.html"
    context_object_name = "records"

    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

    def get_queryset(self):
        queryset = AttendanceRecord.objects.select_related("student__user").order_by("-date")
        request = self.request
        matric_no = request.GET.get("matric_no")
        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")

        if matric_no:
            queryset = queryset.filter(student__matric_no__icontains=matric_no)
        elif start_date and end_date:
            queryset = queryset.filter(date__range=[start_date, end_date])

        return queryset


