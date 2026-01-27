import csv
import pandas as pd
from datetime import datetime
from io import StringIO
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.db import transaction
from .forms import CSVUploadForm
from .models import ImportTask, ErrorLog, Student, Course, Enrolment


class UploadCSVView(View):
    def get(self, request):
        form = CSVUploadForm()
        return render(request, 'importer/upload.html', {'form': form})

    def post(self, request):
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            task = form.save()
            # For production → move to Celery task
            self.process_csv_with_pandas(task)
            return redirect('importer:dashboard')
        return render(request, 'importer/upload.html', {'form': form})

    def process_csv_with_pandas(self, task: ImportTask):
        try:
            file_path = task.uploaded_file.path

            # ── Step 0: Read CSV with pandas ──
            df = pd.read_csv(file_path, dtype=str, keep_default_na=False)
            task.total_rows = len(df)
            task.status = 'CLEANSING'
            task.save()

            # ── Step 1: Data Cleansing ──
            # Strip whitespace from all string columns
            str_cols = df.select_dtypes(include='object').columns
            df[str_cols] = df[str_cols].apply(lambda x: x.str.strip())

            # Replace empty strings with NaN
            df = df.replace('', pd.NA)

            # Optional: drop completely empty rows (if any)
            df = df.dropna(how='all')

            # Log rows that became completely empty after cleansing (rare)
            if len(df) < task.total_rows:
                lost = task.total_rows - len(df)
                ErrorLog.objects.create(
                    task=task,
                    row_number=0,
                    error_message=f"{lost} completely empty rows were removed after cleansing"
                )
                task.total_rows = len(df)

            task.progress = 33
            task.status = 'FORMATTING'
            task.save()

            # ── Step 2: Data Formatting & Validation ──
            errors = []

            # Expected columns (adjust if your CSV has different names)
            expected = {
                'student_id', 'surname', 'first_name', 'birth_date',
                'program', 'registration_date',
                'course_id', 'title', 'start_date', 'lecture_hours',
                'enrolment_date'
            }

            missing_cols = expected - set(df.columns)
            if missing_cols:
                raise ValueError(f"Missing required columns: {', '.join(missing_cols)}")

            # ── Formatting rules ──
            # Dates – try multiple common formats
            date_cols = ['birth_date', 'registration_date', 'start_date', 'enrolment_date']
            for col in date_cols:
                def safe_parse_date(x):
                    if pd.isna(x):
                        return pd.NaT
                    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y.%m.%d'):
                        try:
                            return pd.to_datetime(x, format=fmt, errors='raise').date()
                        except:
                            continue
                    # If we get here, date parsing failed
                    return pd.NaT

                df[col] = df[col].apply(safe_parse_date)

            # Integer
            df['lecture_hours'] = pd.to_numeric(df['lecture_hours'], errors='coerce').fillna(0).astype(int)

            # Create row index for error reporting (1-based)
            df = df.reset_index().rename(columns={'index': 'row_number'})
            df['row_number'] = df['row_number'] + 1

            # Collect rows with critical parsing errors
            invalid_date_rows = df[date_cols].isna().any(axis=1)
            for idx in df[invalid_date_rows]['row_number']:
                errors.append((idx, "Invalid date format in one or more date fields"))

            # Invalid student_id / course_id (basic check)
            df['student_id'] = df['student_id'].astype(str).str.strip()
            df['course_id']  = df['course_id'].astype(str).str.strip()

            invalid_id_rows = df['student_id'].str.len() == 0
            for idx in df[invalid_id_rows]['row_number']:
                errors.append((idx, "Empty or missing student_id"))

            # ── Log formatting errors ──
            for row_num, msg in errors:
                ErrorLog.objects.create(
                    task=task,
                    row_number=row_num,
                    error_message=msg
                )

            # Remove rows with fatal errors (you can adjust this policy)
            df = df[~invalid_date_rows & ~invalid_id_rows]

            task.progress = 66
            task.status = 'IMPORTING'
            task.save()

            # ── Step 3: Import ──
            processed = 0
            with transaction.atomic():
                for _, row in df.iterrows():
                    try:
                        student, _ = Student.objects.get_or_create(
                            student_id=row['student_id'],
                            defaults={
                                'surname': row['surname'] or '',
                                'first_name': row['first_name'] or '',
                                'birth_date': row['birth_date'],
                                'program': row['program'] or '',
                                'registration_date': row['registration_date'],
                            }
                        )

                        course, _ = Course.objects.get_or_create(
                            course_id=row['course_id'],
                            defaults={
                                'title': row['title'] or '',
                                'start_date': row['start_date'],
                                'lecture_hours': row['lecture_hours'],
                            }
                        )

                        Enrolment.objects.get_or_create(
                            student=student,
                            course=course,
                            defaults={'enrolment_date': row['enrolment_date']}
                        )

                        processed += 1
                        task.processed_rows = processed
                        task.save(update_fields=['processed_rows'])
                    except Exception as e:
                        ErrorLog.objects.create(
                            task=task,
                            row_number=row['row_number'],
                            error_message=f"Import failed: {str(e)}"
                        )

            task.progress = 100
            task.status = 'COMPLETED' if processed > 0 else 'FAILED'
            task.save()

        except Exception as e:
            task.status = 'FAILED'
            task.save()
            ErrorLog.objects.create(
                task=task,
                row_number=0,
                error_message=f"Global processing error: {str(e)}"
            )


class DashboardView(View):
    def get(self, request):
        tasks = ImportTask.objects.all().order_by('-created_at')
        return render(request, 'importer/dashboard.html', {'tasks': tasks})

class ErrorLogView(View):
    def get(self, request, task_id):
        task = get_object_or_404(ImportTask, id=task_id)
        errors = task.errors.all()
        return render(request, 'importer/errors.html', {'task': task, 'errors': errors})

class ProgressView(View):
    def get(self, request, task_id):
        task = get_object_or_404(ImportTask, id=task_id)
        data = {
            'status': task.status,
            'progress': task.progress,
            'processed_rows': task.processed_rows,
            'total_rows': task.total_rows,
        }
        return JsonResponse(data)


class ExportDataView(View):
    """View to export Student, Course, and Enrolment data as CSV."""
    
    def get(self, request):
        """Render export selection page."""
        context = {
            'student_count': Student.objects.count(),
            'course_count': Course.objects.count(),
            'enrolment_count': Enrolment.objects.count(),
        }
        return render(request, 'importer/export.html', context)
    
    def post(self, request):
        """Generate CSV file for selected model."""
        model_type = request.POST.get('model_type')
        
        if model_type == 'student':
            queryset = Student.objects.all()
            filename = 'students.csv'
            fields = ['student_id', 'surname', 'first_name', 'birth_date', 
                      'program', 'registration_date', 'created_at', 'updated_at']
        elif model_type == 'course':
            queryset = Course.objects.all()
            filename = 'courses.csv'
            fields = ['course_id', 'title', 'start_date', 'lecture_hours', 
                      'created_at', 'updated_at']
        elif model_type == 'enrolment':
            queryset = Enrolment.objects.all().select_related('student', 'course')
            filename = 'enrolments.csv'
            # Include related fields
            fields = ['student__student_id', 'student__surname', 'student__first_name',
                      'course__course_id', 'course__title', 'enrolment_date', 
                      'created_at', 'updated_at']
        else:
            return HttpResponse('Invalid model type', status=400)
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        
        # Write header
        if model_type == 'enrolment':
            header = ['student_id', 'student_surname', 'student_first_name',
                      'course_id', 'course_title', 'enrolment_date', 
                      'created_at', 'updated_at']
        else:
            header = fields
        writer.writerow(header)
        
        # Write data rows
        for obj in queryset:
            row = []
            if model_type == 'enrolment':
                row.extend([
                    obj.student.student_id,
                    obj.student.surname,
                    obj.student.first_name,
                    obj.course.course_id,
                    obj.course.title,
                    obj.enrolment_date,
                    obj.created_at,
                    obj.updated_at
                ])
            else:
                for field in fields:
                    value = getattr(obj, field)
                    # Format dates properly
                    if isinstance(value, datetime):
                        value = value.strftime('%Y-%m-%d %H:%M:%S')
                    elif hasattr(value, 'strftime'):
                        value = value.strftime('%Y-%m-%d')
                    row.append(value)
            writer.writerow(row)
        
        return response
