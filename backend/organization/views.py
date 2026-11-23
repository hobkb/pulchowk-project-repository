from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from .models import Campus, Department, ResearchGroup
from .serializers import CampusSerializer, DepartmentSerializer, ResearchGroupSerializer

class CampusListView(ListAPIView):
    queryset = Campus.objects.all()
    serializer_class = CampusSerializer
    authentication_classes = []
    permission_classes = [AllowAny]

class DepartmentListView(ListAPIView):
    """
    Public endpoint to list all available departments.
    """
    queryset = Department.objects.all().select_related("campus")
    serializer_class = DepartmentSerializer
    authentication_classes = []
    permission_classes = [AllowAny]

class ResearchGroupListView(ListAPIView):
    serializer_class = ResearchGroupSerializer
    authentication_classes = []
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = ResearchGroup.objects.all().select_related("department")
        department_id = self.request.query_params.get("department_id")
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        return queryset
