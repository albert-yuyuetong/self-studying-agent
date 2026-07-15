import unittest

from backend.main import create_app
from backend.models import DiagnoseRequest, ParentContext
from backend.services.pipeline import TutorWorkflow


class ScaffoldTests(unittest.TestCase):
    def test_app_registers_expected_routes(self) -> None:
        app = create_app()
        self.assertEqual(str(app.url_path_for("health")), "/health")
        self.assertEqual(str(app.url_path_for("framework_overview")), "/api/v1/framework")
        self.assertEqual(str(app.url_path_for("diagnose")), "/api/v1/diagnoses")

    def test_workflow_returns_parent_guidance(self) -> None:
        workflow = TutorWorkflow()
        response = workflow.run(
            DiagnoseRequest(
                student_id="student-001",
                grade="三年级",
                subject="math",
                problem_text="这是一道分数应用题，孩子不会做。",
                expected_answer="3/4",
                student_answer="1/2",
                parent_context=ParentContext(
                    parent_goal="告诉我为什么孩子会错，以及我该怎么讲",
                    feedback="孩子更喜欢看图理解",
                ),
            )
        )

        self.assertEqual(response.profile.learning_style, "visual")
        self.assertEqual(response.diagnosis.error_type, "calculation_mistake")
        self.assertIn("分数运算", response.diagnosis.knowledge_points)
        self.assertEqual(response.architecture_path[0], "interaction")
        self.assertGreaterEqual(len(response.parent_guidance.coaching_steps), 3)


if __name__ == "__main__":
    unittest.main()
