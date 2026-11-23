from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from .models import Campus, Department, ResearchGroup
from .serializers import CampusSerializer, DepartmentSerializer, ResearchGroupSerializer

class CampusListView(ListAPIView):
    queryset = Campus.objects.all()
    serializer_class = CampusSerializer
    permission_classes = [IsAuthenticated]

class DepartmentListView(ListAPIView):
    """
    Lists all departments, for signed-in users (onboarding, filters).
    """
    queryset = Department.objects.all().select_related("campus")
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]

class ResearchGroupListView(ListAPIView):
    serializer_class = ResearchGroupSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = ResearchGroup.objects.all().select_related("department")
        department_id = self.request.query_params.get("department_id")
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        return queryset
