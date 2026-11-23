from rest_framework import serializers
from .models import Campus, Department, ResearchGroup

class CampusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campus
        fields = ("id", "name", "location")

class DepartmentSerializer(serializers.ModelSerializer):
    campus_name = serializers.CharField(source="campus.name", read_only=True)

    class Meta:
        model = Department
        fields = ("id", "name", "campus_name", "campus_id")

class ResearchGroupSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = ResearchGroup
        fields = ("id", "name", "description", "department_id", "department_name")
