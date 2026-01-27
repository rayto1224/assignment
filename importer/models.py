from django.db import models
from django.core.files.storage import FileSystemStorage
import os

# Create your models here.
class Student(models.Model):
    student_id = models.CharField(max_length=10, primary_key=True)
    surname = models.CharField(max_length=20)
    first_name = models.CharField(max_length=20)
    birth_date = models.DateField()
    program = models.CharField(max_length=100)
    registration_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['surname', 'first_name']
    
    def __str__(self):
        return f"{self.student_id} - {self.surname}, {self.first_name}"

class Course(models.Model):
    course_id = models.CharField(max_length=10, primary_key=True)
    title = models.CharField(max_length=50)
    start_date = models.DateField()
    lecture_hours = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['course_id']
    
    def __str__(self):
        return f"{self.course_id}: {self.title}"    
    
class Enrolment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    enrolment_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['student', 'course']
        ordering = ['enrolment_date']
    
    def __str__(self):
        return f"{self.student} in {self.course}"
    
class ImportTask(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('CLEANSING', 'Data Cleansing'),
        ('FORMATTING', 'Data Formatting'),
        ('IMPORTING', 'Importing Data'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]
    
    uploaded_file = models.FileField(upload_to='imports/')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    progress = models.IntegerField(default=0)  # Percentage
    total_rows = models.IntegerField(default=0)
    processed_rows = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Import Task {self.id} - {self.status}"

class ErrorLog(models.Model):
    task = models.ForeignKey(ImportTask, on_delete=models.CASCADE, related_name='errors')
    row_number = models.IntegerField()
    error_message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['row_number']

    def __str__(self):
        return f"Error in row {self.row_number} for task {self.task.id}"