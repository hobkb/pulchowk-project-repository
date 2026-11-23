"""
Onboarding against a repository that already contains extracted people.

Publishing a project creates Student and Faculty rows from names and roll
numbers read out of the PDF. Those rows collide with a real person signing
in later, which is where the "already exists" failures came from. They are
also where the identity risk lives: adopting an existing record is a claim
about who you are, so it must be backed by the verified email rather than
by whatever was typed into the form.
"""

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import Faculty, Student, User
from organization.models import Campus, Department


class OnboardingIdentityTests(APITestCase):
    def setUp(self):
        campus = Campus.objects.get_or_create(name="Pulchowk Campus")[0]
        self.dept = Department.objects.create(name="Dept O", campus=campus)

    def onboard(self, email, payload):
        user = User.objects.create_user(email=email, password="x")
        self.client.force_authenticate(user=user)
        response = self.client.post(
            reverse("acocunts_apis:complete_profile"), payload, format="json"
        )
        user.refresh_from_db()
        return user, response

    # ---------------------------------------------------------------- students

    def test_student_adopts_the_record_extracted_from_their_own_report(self):
        """The roll number comes from the verified address, so this is safe."""
        extracted = Student.objects.create(
            full_name="Old Extracted Name",
            roll_number="080BCT102",
            academic_level="UG",
            email="080bct102.wrongguess@pcampus.edu.np",
            department=self.dept,
        )
        user, response = self.onboard("080bct102.sita@pcampus.edu.np", {
            "role": "student", "full_name": "Sita Sharma",
            "academic_level": "UG", "roll_number": "080BCT102",
            "department_id": self.dept.id,
        })
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Student.objects.filter(roll_number="080BCT102").count(), 1)
        extracted.refresh_from_db()
        self.assertEqual(extracted.id, user.person_id)
        self.assertEqual(extracted.email, "080bct102.sita@pcampus.edu.np")

    def test_a_typed_roll_number_cannot_claim_someone_elses_record(self):
        Student.objects.create(
            full_name="Someone Else", roll_number="079BCT001",
            academic_level="UG", email="079bct001.other@pcampus.edu.np",
        )
        # This address carries no roll number, so the roll is only typed.
        user, response = self.onboard("sita@pcampus.edu.np", {
            "role": "student", "full_name": "Sita Sharma",
            "academic_level": "UG", "roll_number": "079BCT001",
            "department_id": self.dept.id,
        })
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIsNone(user.person_id)

    def test_the_roll_number_in_the_address_wins_over_a_typed_one(self):
        user, response = self.onboard("080bct102.sita@pcampus.edu.np", {
            "role": "student", "full_name": "Sita Sharma",
            "academic_level": "UG",
            "roll_number": "079BCT999",   # someone else's
            "department_id": self.dept.id,
        })
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(user.person.student.roll_number, "080BCT102")

    def test_re_onboarding_updates_rather_than_duplicating(self):
        email = "080bct084.asha@pcampus.edu.np"
        user, first = self.onboard(email, {
            "role": "student", "full_name": "Asha K",
            "academic_level": "UG", "roll_number": "080BCT084",
            "department_id": self.dept.id,
        })
        self.assertEqual(first.status_code, 200, first.data)
        second = self.client.post(reverse("acocunts_apis:complete_profile"), {
            "role": "student", "full_name": "Asha Karki",
            "academic_level": "Masters", "roll_number": "080BCT084",
            "department_id": self.dept.id,
        }, format="json")
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(Student.objects.filter(roll_number="080BCT084").count(), 1)
        user.refresh_from_db()
        self.assertEqual(user.person.student.academic_level, "Masters")

    # ---------------------------------------------------------------- faculty

    def test_typing_a_name_cannot_claim_an_extracted_faculty_record(self):
        """
        The old lookup matched on full_name, so anyone who typed a
        supervisor's name inherited that supervisor's person record --
        including every project already attributed to them.
        """
        supervisor = Faculty.objects.create(
            full_name="Ram Shrestha", designation="Professor",
            email="ram.shrestha@pcampus.edu.np", department=self.dept,
        )
        user, response = self.onboard("impostor@pcampus.edu.np", {
            "role": "faculty", "full_name": "Ram Shrestha",
            "designation": "Professor", "department_id": self.dept.id,
        })
        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotEqual(user.person_id, supervisor.id)
        supervisor.refresh_from_db()
        self.assertEqual(supervisor.email, "ram.shrestha@pcampus.edu.np")

    def test_picking_a_faculty_id_cannot_claim_it_either(self):
        supervisor = Faculty.objects.create(
            full_name="Sita Adhikari", designation="Professor",
            email="sita.adhikari@pcampus.edu.np", department=self.dept,
        )
        user, response = self.onboard("someone.else@pcampus.edu.np", {
            "role": "faculty", "faculty_id": supervisor.id,
            "full_name": "Sita Adhikari", "designation": "Professor",
            "department_id": self.dept.id,
        })
        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotEqual(user.person_id, supervisor.id)

    def test_faculty_matching_their_own_address_does_adopt_the_record(self):
        supervisor = Faculty.objects.create(
            full_name="Hari Bhandari", designation="Professor",
            email="hari.bhandari@pcampus.edu.np", department=self.dept,
        )
        user, response = self.onboard("hari.bhandari@pcampus.edu.np", {
            "role": "faculty", "full_name": "Hari Bhandari",
            "designation": "Associate Professor", "department_id": self.dept.id,
        })
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(user.person_id, supervisor.id)

    def test_an_email_held_by_another_person_is_reported_not_crashed(self):
        Faculty.objects.create(
            full_name="Existing Faculty", email="clash@pcampus.edu.np",
            department=self.dept,
        )
        user, response = self.onboard("clash@pcampus.edu.np", {
            "role": "student", "full_name": "New Student",
            "academic_level": "UG", "roll_number": "081BCT010",
            "department_id": self.dept.id,
        })
        self.assertEqual(response.status_code, 400, getattr(response, "data", None))
        self.assertIsNone(user.person_id)


class ProfileEditingTests(APITestCase):
    """What a person may change about themselves, and what they may not."""

    def setUp(self):
        campus = Campus.objects.get_or_create(name="Pulchowk Campus")[0]
        self.dept = Department.objects.create(name="Dept E", campus=campus)
        self.other_dept = Department.objects.create(name="Dept F", campus=campus)

    def onboard(self, email, payload):
        user = User.objects.create_user(email=email, password="x")
        self.client.force_authenticate(user=user)
        self.client.post(reverse("acocunts_apis:complete_profile"), payload, format="json")
        user.refresh_from_db()
        return user

    def patch(self, payload):
        return self.client.patch(
            reverse("acocunts_apis:my-profile"), payload, format="json"
        )

    def student(self, email="080bct090.ram@pcampus.edu.np"):
        return self.onboard(email, {
            "role": "student", "full_name": "Ram T",
            "academic_level": "UG", "roll_number": "080BCT090",
            "department_id": self.dept.id,
        })

    def test_a_student_can_correct_their_name_level_and_department(self):
        user = self.student()
        response = self.patch({
            "full_name": "Ram Thapa",
            "academic_level": "Masters",
            "department_id": self.other_dept.id,
        })
        self.assertEqual(response.status_code, 200, response.data)
        user.refresh_from_db()
        self.assertEqual(user.person.full_name, "Ram Thapa")
        self.assertEqual(user.person.student.academic_level, "Masters")
        self.assertEqual(user.person.department_id, self.other_dept.id)

    def test_a_roll_number_proven_by_the_address_cannot_be_changed(self):
        user = self.student()
        response = self.patch({"roll_number": "079BCT001"})
        self.assertEqual(response.status_code, 200, response.data)
        user.refresh_from_db()
        self.assertEqual(user.person.student.roll_number, "080BCT090")
        self.assertTrue(response.data["data"]["profile"]["roll_number_locked"])

    def test_a_typed_roll_number_can_be_corrected_but_not_stolen(self):
        # This address carries no roll number, so the field stays editable.
        user = self.onboard("bina@pcampus.edu.np", {
            "role": "student", "full_name": "Bina G",
            "academic_level": "UG", "roll_number": "081BCT050",
            "department_id": self.dept.id,
        })
        self.assertFalse(
            self.client.get(reverse("acocunts_apis:fetch_user"))
            .data["data"]["profile"]["roll_number_locked"]
        )
        self.assertEqual(self.patch({"roll_number": "081BCT051"}).status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.person.student.roll_number, "081BCT051")

        Student.objects.create(
            full_name="Held", roll_number="075BCT002", academic_level="UG",
            email="075bct002.held@pcampus.edu.np",
        )
        self.assertEqual(self.patch({"roll_number": "075BCT002"}).status_code, 400)

    def test_editing_cannot_change_the_role_or_the_email(self):
        user = self.student("080bct091.gita@pcampus.edu.np")
        response = self.patch({
            "full_name": "Gita S",
            "role": "admin", "is_staff": True, "is_superuser": True,
            "email": "attacker@pcampus.edu.np",
        })
        self.assertEqual(response.status_code, 200, response.data)
        user.refresh_from_db()
        self.assertEqual(user.role, "student")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.email, "080bct091.gita@pcampus.edu.np")
        self.assertEqual(user.person.email, "080bct091.gita@pcampus.edu.np")

    def test_editing_requires_a_completed_profile(self):
        user = User.objects.create_user(email="fresh@pcampus.edu.np", password="x")
        self.client.force_authenticate(user=user)
        self.assertEqual(self.patch({"full_name": "X"}).status_code, 400)
