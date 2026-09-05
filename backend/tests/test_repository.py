"""Storage tests run with unittest as well as pytest; no model calls needed."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from app.repositories.profile_repository import RepositoryConflict, RepositoryNotFound, SQLiteTutorRepository
from app.schemas.diagnosis import (
    FeedbackRequest, Lesson, LessonStep, SkillEvidence, TeachingStrategy, TutorRequest, TutorResponse,
)
from app.schemas.profile import ProfileSettings, StudentProfile


def make_turn(number: int = 1, **kwargs) -> tuple[TutorRequest, TutorResponse]:
    req = TutorRequest(
        student_id=kwargs.pop("student_id", "student"),
        session_id=kwargs.pop("session_id", "session"),
        request_id=f"request-{number}",
        problem_text="请根据两份历史材料评价作者观点。",
        student_answer="材料甲的作者在战后写作，可能存在回忆偏差。",
        **kwargs,
    )
    response = TutorResponse(
        student_id=req.student_id,
        session_id=req.session_id,
        request_id=req.request_id,
        turn_id=f"turn-{number}",
        status="completed",
        guidance_mode="post-answer",
        strategy=TeachingStrategy(approach="对照材料并追问证据", rationale=["检查论点的来源"], profile_used=[], pace="balanced"),
        lesson=Lesson(
            title="检查材料来源", goal="用来源判断材料能支持什么结论",
            steps=[LessonStep(title="标出来源", explanation="先找作者和写作时间。", question="写作时间有什么影响？", checkpoint="能区分写作时间和事件时间")],
            understanding_checks=["作者身份可能怎样影响叙述？"], recap="结论必须受到证据范围的约束。",
        ),
        profile=StudentProfile(student_id=req.student_id),
    )
    return req, response


def evidence(*, subject="历史", name="史料来源分析", outcome="demonstrated") -> SkillEvidence:
    return SkillEvidence(subject=subject, name=name, outcome=outcome, evidence="指出战后回忆与现场记录的区别。", confidence=0.95)


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.db_path = str(Path(self.directory.name) / "tutor.sqlite3")
        self.repo = SQLiteTutorRepository(self.db_path)

    def tearDown(self):
        self.repo.close()
        self.directory.cleanup()

    def commit(self, number=1, *, attempt_key=None, items=None, **kwargs):
        req, response = make_turn(number, **kwargs)
        return self.repo.commit_turn(req, response, f"fingerprint-{number}", attempt_key or f"attempt-{number}", [evidence()] if items is None else items)

    def feedback(self, **kwargs):
        payload = dict(feedback_id="feedback-1", student_id="student", session_id="session", turn_id="turn-1", useful=True, child_understood=False, comment="还不理解为什么要比较来源。")
        payload.update(kwargs)
        return FeedbackRequest(**payload)

    def test_profile_and_turn_survive_new_repository_instance(self):
        self.repo.update_profile("student", ProfileSettings(grade="高中", interests=["历史"]))
        self.commit()
        reopened = SQLiteTutorRepository(self.db_path)
        try:
            profile = reopened.get_or_create("student")
            self.assertEqual(profile.grade, "高中")
            self.assertEqual(next(iter(profile.skills.values())).demonstrated_count, 1)
            self.assertEqual(reopened.history("student", "session")[0]["request"]["student_answer"], "材料甲的作者在战后写作，可能存在回忆偏差。")
            self.assertEqual(reopened.get_cached("student", "request-1", "fingerprint-1").turn_id, "turn-1")
        finally:
            reopened.close()

    def test_memory_repository_uses_independent_model_objects(self):
        repo = SQLiteTutorRepository(":memory:")
        try:
            profile = repo.get_or_create("student")
            profile.interests.append("should not leak")
            self.assertEqual(repo.get_or_create("student").interests, [])
        finally:
            repo.close()

    def test_profile_settings_preserve_observed_skills_and_feedback(self):
        original = self.commit()
        self.repo.record_feedback(self.feedback())
        profile = self.repo.update_profile("student", ProfileSettings(grade="高二", preferred_explanation_modes=["材料对照"]))
        self.assertEqual(profile.skills, original.profile.skills)
        self.assertEqual(profile.format_feedback["对照材料并追问证据"].helpful, 1)
        self.assertEqual(profile.grade, "高二")

    def test_memory_repository_also_merges_concurrent_turns(self):
        repo = SQLiteTutorRepository(":memory:")
        try:
            def store(number):
                req, response = make_turn(number)
                return repo.commit_turn(req, response, str(number), str(number), [evidence()])
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(store, range(1, 17)))
            self.assertEqual(next(iter(repo.get_or_create("student").skills.values())).demonstrated_count, 16)
        finally:
            repo.close()

    def test_same_request_is_idempotent_and_different_payload_conflicts(self):
        original = self.commit()
        req, response = make_turn()
        response.turn_id = "regenerated-turn"
        replay = self.repo.commit_turn(req, response, "fingerprint-1", "another-attempt", [evidence()])
        self.assertEqual(original, replay)
        self.assertEqual(len(self.repo.history("student", "session")), 1)
        with self.assertRaises(RepositoryConflict):
            self.repo.get_cached("student", "request-1", "different")
        with self.assertRaises(RepositoryConflict):
            self.repo.commit_turn(req, response, "different", "another-attempt", [evidence()])

    def test_attempt_deduplication_does_not_recount_reexplanation(self):
        self.commit(attempt_key="same-answer")
        repeated = self.commit(2, attempt_key="same-answer")
        self.assertEqual(next(iter(repeated.profile.skills.values())).demonstrated_count, 1)
        self.assertTrue(any("未重复" in note for note in repeated.profile_updates))
        self.assertEqual(len(self.repo.history("student", "session")), 2)

    def test_degraded_and_empty_evidence_do_not_consume_attempt(self):
        req, response = make_turn()
        response.status = "degraded"
        degraded = self.repo.commit_turn(req, response, "fingerprint-1", "answer", [evidence()])
        self.assertEqual(degraded.profile.skills, {})
        self.commit(2, attempt_key="answer", items=[])
        reliable = self.commit(3, attempt_key="answer")
        self.assertEqual(next(iter(reliable.profile.skills.values())).demonstrated_count, 1)

    def test_normalized_skill_has_one_outcome_per_turn_and_subject_boundary(self):
        items = [evidence(subject="English", name="Source  Analysis"), evidence(subject="Ｅｎｇｌｉｓｈ", name="source analysis"), evidence(subject="History", name="source analysis")]
        response = self.commit(items=items)
        self.assertEqual(len(response.profile.skills), 2)
        self.assertTrue(all(skill.demonstrated_count == 1 for skill in response.profile.skills.values()))

    def test_contradictory_evidence_is_not_counted(self):
        response = self.commit(items=[evidence(), evidence(outcome="needs-support")], attempt_key="answer")
        self.assertEqual(response.profile.skills, {})
        reliable = self.commit(2, attempt_key="answer")
        self.assertEqual(next(iter(reliable.profile.skills.values())).demonstrated_count, 1)

    def test_session_ownership_and_feedback_turn_ownership(self):
        self.commit()
        for action in (
            lambda: self.repo.ensure_session("other", "session"),
            lambda: self.repo.history("other", "session"),
            lambda: self.repo.session_turns("other", "session"),
            lambda: self.repo.record_feedback(self.feedback(student_id="other")),
        ):
            with self.assertRaises(RepositoryNotFound):
                action()
        self.repo.ensure_session("student", "other-session")
        with self.assertRaises(RepositoryNotFound):
            self.repo.record_feedback(self.feedback(session_id="other-session"))
        req, response = make_turn(2, student_id="other")
        with self.assertRaises(RepositoryNotFound):
            self.repo.commit_turn(req, response, "fingerprint-2", "answer", [evidence()])

    def test_feedback_is_idempotent_and_does_not_update_skills(self):
        original = self.commit()
        result = self.repo.record_feedback(self.feedback())
        replay = self.repo.record_feedback(self.feedback())
        alias = self.repo.record_feedback(self.feedback(feedback_id="another-id"))
        self.assertFalse(result["duplicate"])
        self.assertTrue(replay["duplicate"])
        self.assertTrue(alias["duplicate"])
        self.assertEqual(alias["profile"].format_feedback["对照材料并追问证据"].helpful, 1)
        self.assertEqual(alias["profile"].skills, original.profile.skills)
        feedback = self.repo.history("student", "session")[0]["feedback"]
        self.assertFalse(feedback["child_understood"])
        self.assertEqual(feedback["comment"], "还不理解为什么要比较来源。")
        for feedback_id in ("feedback-1", "new-feedback-id", "another-id"):
            with self.assertRaises(RepositoryConflict):
                self.repo.record_feedback(self.feedback(feedback_id=feedback_id, useful=False))

    def test_feedback_requires_an_actual_lesson(self):
        req, response = make_turn()
        response.lesson = None
        self.repo.commit_turn(req, response, "fingerprint-1", None, [])
        with self.assertRaises(RepositoryConflict):
            self.repo.record_feedback(self.feedback())

    def test_images_are_replaced_by_hashes_and_follow_up_is_retained(self):
        image_data = "data:image/png;base64,aW1hZ2UtYnl0ZXM="
        self.commit(attachments=[image_data], follow_up="请解释第三步。")
        history = self.repo.history("student", "session")
        self.assertNotIn("aW1hZ2UtYnl0ZXM=", json.dumps(history))
        self.assertIn("sha256=", history[0]["request"]["attachments"][0])
        self.assertEqual(history[0]["request"]["follow_up"], "请解释第三步。")
        with closing(sqlite3.connect(self.db_path)) as conn:
            stored = conn.execute("SELECT request_json FROM turns").fetchone()[0]
        self.assertNotIn(image_data, stored)

    def test_concurrent_distinct_turns_merge_into_latest_profile(self):
        # Every response starts with an empty snapshot, as concurrent model calls do.
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda n: self.commit(n), range(1, 17)))
        profile = self.repo.get_or_create("student")
        self.assertEqual(next(iter(profile.skills.values())).demonstrated_count, 16)
        self.assertEqual(sorted(next(iter(result.profile.skills.values())).demonstrated_count for result in results), list(range(1, 17)))
        self.assertEqual(len(self.repo.session_turns("student", "session")["turns"]), 16)

    def test_concurrent_same_request_and_attempt_are_counted_once(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.commit(), range(8)))
        self.assertTrue(all(result == results[0] for result in results))
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda n: self.commit(n, attempt_key="attempt-1"), range(2, 10)))
        self.assertEqual(next(iter(self.repo.get_or_create("student").skills.values())).demonstrated_count, 1)

    def test_history_and_session_turns_are_bounded_and_chronological(self):
        for number in range(1, 55):
            self.commit(number, items=[])
        history = self.repo.history("student", "session", limit=3)
        self.assertEqual([turn["response"]["turn_id"] for turn in history], ["turn-52", "turn-53", "turn-54"])
        turns = self.repo.session_turns("student", "session")["turns"]
        self.assertEqual(len(turns), 50)
        self.assertEqual(turns[0]["turn_id"], "turn-5")


if __name__ == "__main__":
    unittest.main()
