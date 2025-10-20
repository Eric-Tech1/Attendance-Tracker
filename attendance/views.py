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
from webauthn.helpers import options_to_json
from webauthn.helpers.structs import PublicKeyCredentialRequestOptions
from webauthn import verify_authentication_response
import os, json, base64
from django.http import JsonResponse, HttpResponseNotAllowed
from django.conf import settings

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

        ctx['student'] = student  # ✅ ADD THIS LINE
        ctx['today_record'] = AttendanceRecord.objects.filter(student=student, date=today).first()
        ctx['now'] = timezone.now()
        ctx['records'] = AttendanceRecord.objects.filter(student=student).order_by('-date')[:10]
        ctx['locations'] = Location.objects.all()
        ctx['student'] = student


        return ctx



@login_required
def check_in(request):
    """Handle student check-in with GPS validation, fingerprint verification, and duplicate prevention."""
    student = get_object_or_404(Student, user=request.user)

    # ✅ Step 0: Ensure student has registered a fingerprint
    if not student.webauthn_credential_id or not student.webauthn_public_key:
        messages.error(request, "⚠️ You must register your fingerprint before checking in.")
        return redirect("attendance:student_dashboard")

    if request.method == "POST":
        location_id = request.POST.get("location")
        user_lat = request.POST.get("latitude")
        user_lon = request.POST.get("longitude")
        assertion = request.POST.get("assertion")

        # ✅ Step 1: Ensure all required data
        if not location_id or not user_lat or not user_lon:
            messages.error(request, "⚠️ Missing location or GPS data.")
            return redirect("attendance:student_dashboard")

        if not assertion:
            messages.error(request, "⚠️ Fingerprint verification required.")
            return redirect("attendance:student_dashboard")

        # ✅ Step 2: Fingerprint verification
        try:
            if "webauthn_challenge" not in request.session:
                messages.error(request, "⚠️ Fingerprint challenge expired. Try again.")
                return redirect("attendance:student_dashboard")

            verification = verify_authentication_response(
                credential=assertion,
                expected_challenge=request.session.pop("webauthn_challenge"),
                expected_rp_id="your-domain.com",  # 🔹 replace with your domain
                expected_origin="https://your-domain.com",  # 🔹 replace with your frontend origin
                credential_public_key=student.webauthn_public_key,
                credential_current_sign_count=student.webauthn_sign_count,
                require_user_verification=True,
            )

            # Update sign count (prevent replay attacks)
            student.webauthn_sign_count = verification.new_sign_count
            student.save()

        except Exception as e:
            print("⚠️ Fingerprint verification failed:", e)
            messages.error(request, "❌ Fingerprint verification failed. Try again.")
            return redirect("attendance:student_dashboard")

        # ✅ Step 3: GPS & Attendance handling
        try:
            location = get_object_or_404(Location, id=location_id)

            user_lat, user_lon = float(user_lat), float(user_lon)
            loc_lat, loc_lon = float(location.latitude), float(location.longitude)
            allowed_radius = float(location.allowed_radius)

            distance = calculate_distance(user_lat, user_lon, loc_lat, loc_lon)
            print(f"📍 Distance from {location.name}: {distance:.2f}m (allowed: {allowed_radius}m)")

            if distance > allowed_radius:
                messages.error(request, f"❌ Too far from {location.name}. Move closer to check in.")
                return redirect("attendance:student_dashboard")

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

            if not created:  # record exists
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

@login_required
def register_fingerprint_page(request):
    """Render the fingerprint registration template."""
    student = get_object_or_404(Student, user=request.user)
    return render(request, "attendance/register_fingerprint.html", {"student": student})

def b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode('ascii')

def b64url_decode(s: str) -> bytes:
    padding = '=' * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + padding)

@login_required
def webauthn_register_begin(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    student = Student.objects.get(user=request.user)

    # 1) Create a random challenge and save in session (must match verification later)
    challenge = os.urandom(32)
    request.session['webauthn_registration_challenge'] = b64url_encode(challenge)

    # 2) Build publicKey options object (we return JSON that the front-end will consume)
    publicKey = {
        "challenge": b64url_encode(challenge),
        "rp": {"name": "Attendance Tracker", "id": settings.RP_ID if hasattr(settings, "RP_ID") else request.get_host()},
        # user.id must be bytes; convert student.pk or username to bytes
        "user": {
            "id": b64url_encode(str(student.pk).encode('utf-8')),
            "name": request.user.username,
            "displayName": request.user.get_full_name() or request.user.username
        },
        "pubKeyCredParams": [
            {"type": "public-key", "alg": -7},  # ES256
            {"type": "public-key", "alg": -257} # RS256 (optional)
        ],
        "timeout": 60000,
        # You can include excludeCredentials here to prevent re-registering same authenticator
        # "excludeCredentials": [...]
        # "authenticatorSelection": {"authenticatorAttachment":"platform", "userVerification":"required"}
    }

    return JsonResponse({"publicKey": publicKey})


@login_required
def webauthn_register_complete(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    body = json.loads(request.body)
    # body contains id, rawId (base64url), response: {clientDataJSON, attestationObject}

    # You must verify attestation using a WebAuthn library (example pseudo):
    #   verification = verify_registration_response(
    #       credential=body,
    #       expected_challenge=request.session.get('webauthn_registration_challenge'),
    #       expected_rp_id=settings.RP_ID,
    #       expected_origin=settings.ORIGIN,
    #       require_user_verification=True,
    #   )
    #
    # Then store verification.credential_public_key and verification.credential_id
    #
    # Below is a *placeholder* flow (you must use a real verify_* call from your webauthn library).

    try:
        # Example using a library (pseudo)
        # verification = your_webauthn_lib.verify_attestation(body, expected_challenge, ...)
        # credential_id_bytes = b64url_decode(body['rawId'])
        # public_key_bytes = verification.credential_public_key
        # sign_count = verification.sign_count

        # For illustration only (do NOT use as real verification):
        credential_id_bytes = b64url_decode(body.get('rawId'))
        public_key_bytes = b'PLACEHOLDER_PUBLIC_KEY'  # replace with real key from verification
        sign_count = 0

        # Save on Student model fields (Student has BinaryFields we discussed earlier)
        student = Student.objects.get(user=request.user)
        student.webauthn_credential_id = credential_id_bytes
        student.webauthn_public_key = public_key_bytes
        student.webauthn_sign_count = sign_count
        student.save()

        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)
    
@login_required
def webauthn_authenticate_begin(request):
    student = Student.objects.get(user=request.user)
    challenge = os.urandom(32)
    request.session['webauthn_auth_challenge'] = b64url_encode(challenge)

    publicKey = {
        "challenge": b64url_encode(challenge),
        "timeout": 60000,
        "rpId": settings.RP_ID if hasattr(settings, "RP_ID") else request.get_host(),
        "allowCredentials": [
            {"type": "public-key", "id": b64url_encode(student.webauthn_credential_id)}
        ],
        "userVerification": "required"
    }
    return JsonResponse({"publicKey": publicKey})

@login_required
def webauthn_authenticate_complete(request):
    body = json.loads(request.body)
    # Here you would verify the assertion using a WebAuthn library
    # verify_authentication_response(...)
    try:
        # pseudo verification
        student = Student.objects.get(user=request.user)
        student.webauthn_sign_count += 1
        student.save()
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)
