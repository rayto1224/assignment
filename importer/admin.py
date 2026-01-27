from django.contrib import admin
from . models import Student, Course, Enrolment, ImportTask, ErrorLog
# Register your models here.

class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_id','surname','first_name','birth_date','program','registration_date')
    list_display_links = ('student_id','surname')
    search_fields = ('surname','first_name')
    list_per_page = 10

class CourseAdmin(admin.ModelAdmin):
    list_display = ('course_id','title','start_date','lecture_hours')
    list_display_links = ('course_id','title')
    search_fields = ('course_id','title')
    list_per_page = 10

class EnrolmentAdmin(admin.ModelAdmin):
    list_display = ('student','course','enrolment_date')
    list_display_links = ('student','course')
    search_fields = ('student__surname','student__first_name','course__title')
    list_per_page = 10

class ErrorLogAdmin(admin.ModelAdmin):
    list_display = ('task_id','row_number','error_message')
    list_display_links = ('task_id',)
    search_fields = ('error_message',)
    list_per_page = 10

class ImportTaskAdmin(admin.ModelAdmin):
    list_display = ('id','status','progress','total_rows','created_at')
    list_display_links = ('created_at',)
    search_fields = ('status',)
    list_per_page = 10

admin.site.register(Student, StudentAdmin)
admin.site.register(Course, CourseAdmin)
admin.site.register(Enrolment, EnrolmentAdmin)
admin.site.register(ErrorLog, ErrorLogAdmin)
admin.site.register(ImportTask, ImportTaskAdmin)
