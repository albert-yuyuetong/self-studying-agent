"""Persist observed evidence and teaching feedback with transactional receipts."""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Iterator
import unicodedata
from uuid import uuid4

from app.schemas.diagnosis import FeedbackRequest, SkillEvidence, TutorRequest, TutorResponse
from app.schemas.profile import FormatFeedback, ProfileSettings, SkillState, StudentProfile


class RepositoryConflict(Exception):
    """An idempotency key or an existing turn has different content."""


class RepositoryNotFound(Exception):
    """A session or turn is absent, including when owned by another student."""


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def _skill_key(evidence: SkillEvidence) -> str:
    # Preserve the boundary even if a label contains punctuation.
    return _json([_normalized(evidence.subject), _normalized(evidence.name)])


class SQLiteTutorRepository:
    def __init__(self, path: str) -> None:
        self._anchor: sqlite3.Connection | None = None
        self._uri = path == ":memory:"
        # SQLite shared-cache memory DBs report SQLITE_LOCKED immediately instead
        # of honoring busy_timeout. Serialize their connections within this owner.
        self._connection_lock = RLock() if self._uri else nullcontext()
        if self._uri:
            self._path = f"file:tutor-{uuid4().hex}?mode=memory&cache=shared"
            # Retain an anchor so per-operation connections share this memory DB.
            self._anchor = self._connect(check_same_thread=False)
        else:
            location = Path(path).expanduser().resolve()
            location.parent.mkdir(parents=True, exist_ok=True)
            self._path = str(location)
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS profiles (
                    student_id TEXT PRIMARY KEY, profile_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    student_id TEXT NOT NULL REFERENCES profiles(student_id),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS turns (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    turn_id TEXT NOT NULL UNIQUE,
                    student_id TEXT NOT NULL REFERENCES profiles(student_id),
                    session_id TEXT NOT NULL REFERENCES sessions(session_id),
                    request_id TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(student_id, request_id)
                );
                CREATE INDEX IF NOT EXISTS turns_session_sequence
                    ON turns(session_id, sequence);
                CREATE TABLE IF NOT EXISTS attempts (
                    student_id TEXT NOT NULL REFERENCES profiles(student_id),
                    attempt_key TEXT NOT NULL,
                    turn_id TEXT NOT NULL REFERENCES turns(turn_id),
                    PRIMARY KEY(student_id, attempt_key)
                );
                CREATE TABLE IF NOT EXISTS turn_feedback (
                    turn_id TEXT PRIMARY KEY REFERENCES turns(turn_id),
                    payload_fingerprint TEXT NOT NULL,
                    feedback_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS feedback_receipts (
                    student_id TEXT NOT NULL REFERENCES profiles(student_id),
                    feedback_id TEXT NOT NULL,
                    turn_id TEXT NOT NULL REFERENCES turns(turn_id),
                    payload_fingerprint TEXT NOT NULL,
                    PRIMARY KEY(student_id, feedback_id)
                );
                """
            )

    def _connect(self, *, check_same_thread: bool = True) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, uri=self._uri, timeout=15, isolation_level=None, check_same_thread=check_same_thread)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=15000")
        return conn

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        with self._connection_lock:
            conn = self._connect()
            try:
                yield conn
            finally:
                conn.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    def close(self) -> None:
        if self._anchor is not None:
            self._anchor.close()
            self._anchor = None

    @staticmethod
    def _profile(conn: sqlite3.Connection, student_id: str) -> StudentProfile:
        row = conn.execute("SELECT profile_json FROM profiles WHERE student_id=?", (student_id,)).fetchone()
        if row:
            return StudentProfile.model_validate_json(row["profile_json"])
        profile = StudentProfile(student_id=student_id)
        conn.execute("INSERT INTO profiles(student_id, profile_json) VALUES (?, ?)", (student_id, profile.model_dump_json()))
        return profile

    @staticmethod
    def _save_profile(conn: sqlite3.Connection, profile: StudentProfile) -> None:
        conn.execute("UPDATE profiles SET profile_json=? WHERE student_id=?", (profile.model_dump_json(), profile.student_id))

    @staticmethod
    def _check_session(conn: sqlite3.Connection, student_id: str, session_id: str, *, create: bool = False) -> None:
        row = conn.execute("SELECT student_id FROM sessions WHERE session_id=?", (session_id,)).fetchone()
        if row is not None:
            if row["student_id"] != student_id:
                raise RepositoryNotFound("找不到该学习会话")
            return
        if not create:
            raise RepositoryNotFound("找不到该学习会话")
        SQLiteTutorRepository._profile(conn, student_id)
        conn.execute("INSERT INTO sessions(session_id, student_id, created_at) VALUES (?, ?, ?)", (session_id, student_id, _now()))

    @staticmethod
    def _cached(conn: sqlite3.Connection, student_id: str, request_id: str, fingerprint: str) -> TutorResponse | None:
        row = conn.execute(
            "SELECT fingerprint, response_json FROM turns WHERE student_id=? AND request_id=?",
            (student_id, request_id),
        ).fetchone()
        if row is None:
            return None
        if row["fingerprint"] != fingerprint:
            raise RepositoryConflict("request_id 已用于不同请求，请使用新的 request_id")
        return TutorResponse.model_validate_json(row["response_json"])

    def get_or_create(self, student_id: str) -> StudentProfile:
        with self._transaction() as conn:
            return self._profile(conn, student_id)

    def update_profile(self, student_id: str, settings: ProfileSettings) -> StudentProfile:
        with self._transaction() as conn:
            profile = self._profile(conn, student_id)
            # Never copy caller-supplied derived state, even for a model subclass.
            for field in ProfileSettings.model_fields:
                setattr(profile, field, getattr(settings, field))
            self._save_profile(conn, profile)
            return profile.model_copy(deep=True)

    def ensure_session(self, student_id: str, session_id: str) -> None:
        with self._transaction() as conn:
            self._check_session(conn, student_id, session_id, create=True)

    def get_cached(self, student_id: str, request_id: str, fingerprint: str) -> TutorResponse | None:
        with self._connection() as conn:
            return self._cached(conn, student_id, request_id, fingerprint)

    def history(self, student_id: str, session_id: str, limit: int = 6) -> list[dict]:
        with self._connection() as conn:
            self._check_session(conn, student_id, session_id)
            rows = conn.execute(
                """SELECT t.request_json, t.response_json, f.feedback_json
                   FROM turns t LEFT JOIN turn_feedback f ON f.turn_id=t.turn_id
                   WHERE t.student_id=? AND t.session_id=?
                   ORDER BY t.sequence DESC LIMIT ?""",
                (student_id, session_id, max(0, min(limit, 50))),
            ).fetchall()
            return [
                {
                    "request": json.loads(row["request_json"]),
                    "response": json.loads(row["response_json"]),
                    "feedback": json.loads(row["feedback_json"]) if row["feedback_json"] else None,
                }
                for row in reversed(rows)
            ]

    @staticmethod
    def _stored_request(req: TutorRequest) -> dict:
        payload = req.model_dump(mode="json")
        payload["attachments"] = [
            f"[图片已在本轮分析中读取；sha256={hashlib.sha256(value.encode('utf-8')).hexdigest()}]"
            for value in req.attachments
        ]
        return payload

    @staticmethod
    def _unique_evidence(evidence: list[SkillEvidence]) -> tuple[dict[str, SkillEvidence], list[str]]:
        chosen: dict[str, SkillEvidence] = {}
        conflicts: set[str] = set()
        notes: list[str] = []
        for item in evidence:
            key = _skill_key(item)
            if key in conflicts:
                continue
            previous = chosen.get(key)
            if previous and previous.outcome != item.outcome:
                conflicts.add(key)
                chosen.pop(key)
                notes.append(f"{item.name}的本轮证据互相矛盾，未更新该知识点。")
            elif previous is None or item.confidence > previous.confidence:
                chosen[key] = item
        return chosen, notes

    def commit_turn(
        self,
        req: TutorRequest,
        response: TutorResponse,
        fingerprint: str,
        attempt_key: str | None,
        evidence: list[SkillEvidence],
    ) -> TutorResponse:
        if response.student_id != req.student_id or (req.request_id and response.request_id != req.request_id):
            raise RepositoryConflict("请求与结果身份不一致")
        if req.session_id and req.session_id != response.session_id:
            raise RepositoryConflict("请求与结果会话不一致")
        with self._transaction() as conn:
            cached = self._cached(conn, req.student_id, response.request_id, fingerprint)
            if cached is not None:
                return cached
            self._check_session(conn, req.student_id, response.session_id, create=True)
            profile = self._profile(conn, req.student_id)
            result = response.model_copy(deep=True)
            result.profile_updates = []
            accepted, notes = self._unique_evidence(evidence) if response.status == "completed" else ({}, [])
            result.profile_updates.extend(notes)
            consumed = bool(attempt_key and conn.execute(
                "SELECT 1 FROM attempts WHERE student_id=? AND attempt_key=?", (req.student_id, attempt_key)
            ).fetchone())
            if consumed:
                result.profile_updates.append("这份作答已记录学习证据，本次讲解未重复更新知识点。")
            elif accepted:
                for key, item in accepted.items():
                    skill = profile.skills.get(key) or SkillState(subject=item.subject, name=item.name)
                    if item.outcome == "demonstrated":
                        skill.demonstrated_count += 1
                        label = "展示理解"
                    else:
                        skill.needs_support_count += 1
                        label = "需要支持"
                    skill.last_evidence = item.evidence
                    skill.last_seen = _now()
                    profile.skills[key] = skill
                    result.profile_updates.append(f"{item.subject} · {item.name}：新增一条{label}的作答证据。")
                self._save_profile(conn, profile)
            result.profile = profile
            try:
                conn.execute(
                    """INSERT INTO turns(turn_id, student_id, session_id, request_id, fingerprint,
                       request_json, response_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        result.turn_id, req.student_id, result.session_id, result.request_id, fingerprint,
                        _json(self._stored_request(req)), result.model_dump_json(), _now(),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise RepositoryConflict("该 turn_id 已被使用，请创建新的教学轮次") from exc
            # Empty or unreliable evidence must not reserve an attempt forever.
            if accepted and not consumed and attempt_key:
                conn.execute("INSERT INTO attempts(student_id, attempt_key, turn_id) VALUES (?, ?, ?)", (req.student_id, attempt_key, result.turn_id))
            return result

    def record_feedback(self, req: FeedbackRequest) -> dict:
        canonical = req.model_dump(mode="json", exclude={"feedback_id"})
        fingerprint = hashlib.sha256(_json(canonical).encode("utf-8")).hexdigest()
        with self._transaction() as conn:
            self._check_session(conn, req.student_id, req.session_id)
            row = conn.execute(
                "SELECT response_json FROM turns WHERE turn_id=? AND student_id=? AND session_id=?",
                (req.turn_id, req.student_id, req.session_id),
            ).fetchone()
            if row is None:
                raise RepositoryNotFound("找不到该教学轮次")
            turn = TutorResponse.model_validate_json(row["response_json"])
            if turn.status != "completed" or turn.lesson is None or turn.strategy is None or not turn.strategy.approach.strip():
                raise RepositoryConflict("该轮次没有可评价的完整讲解")
            receipt = conn.execute(
                "SELECT payload_fingerprint FROM feedback_receipts WHERE student_id=? AND feedback_id=?",
                (req.student_id, req.feedback_id),
            ).fetchone()
            if receipt is not None:
                if receipt["payload_fingerprint"] != fingerprint:
                    raise RepositoryConflict("feedback_id 已用于不同反馈，请使用新的 feedback_id")
                return {"profile": self._profile(conn, req.student_id), "duplicate": True}
            existing = conn.execute("SELECT payload_fingerprint FROM turn_feedback WHERE turn_id=?", (req.turn_id,)).fetchone()
            if existing and existing["payload_fingerprint"] != fingerprint:
                raise RepositoryConflict("该教学轮次已有反馈，不能重复提交不同评价")
            profile = self._profile(conn, req.student_id)
            duplicate = existing is not None
            if not duplicate:
                approach = turn.strategy.approach
                feedback = profile.format_feedback.get(approach) or FormatFeedback()
                if req.useful:
                    feedback.helpful += 1
                else:
                    feedback.unhelpful += 1
                profile.format_feedback[approach] = feedback
                self._save_profile(conn, profile)
                conn.execute(
                    "INSERT INTO turn_feedback(turn_id, payload_fingerprint, feedback_json, created_at) VALUES (?, ?, ?, ?)",
                    (req.turn_id, fingerprint, req.model_dump_json(), _now()),
                )
            conn.execute(
                "INSERT INTO feedback_receipts(student_id, feedback_id, turn_id, payload_fingerprint) VALUES (?, ?, ?, ?)",
                (req.student_id, req.feedback_id, req.turn_id, fingerprint),
            )
            return {"profile": profile, "duplicate": duplicate}

    def session_turns(self, student_id: str, session_id: str) -> dict:
        with self._connection() as conn:
            self._check_session(conn, student_id, session_id)
            rows = conn.execute(
                "SELECT response_json FROM turns WHERE student_id=? AND session_id=? ORDER BY sequence DESC LIMIT 50",
                (student_id, session_id),
            ).fetchall()
            return {"session_id": session_id, "student_id": student_id, "turns": [json.loads(row["response_json"]) for row in reversed(rows)]}
