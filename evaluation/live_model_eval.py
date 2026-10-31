"""Opt-in paid-model evaluation against synthetic, self-contained tasks.

Run from repository root. Never imported by pytest. Uses the configured model,
an in-memory database, and writes only synthetic inputs/model outputs to --out.
No API keys or HTTP headers are logged. A completed status is NOT a quality score.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
# Do this before importing app.main (which builds its default app).
os.environ["DATABASE_PATH"] = ":memory:"

from fastapi.testclient import TestClient
from app.core.config import settings
from app.main import create_app
from app.repositories.profile_repository import SQLiteTutorRepository
from app.services.llm_client import LLMClient
from app.services.tutor_engine import TutorEngine
from app.schemas.diagnosis import FeedbackRequest, TutorRequest, TutorResponse
from app.schemas.profile import ProfileSettings
from app.orchestration.tutor_orchestrator import payload_fingerprint


DENSITY = {
    "subject": "物理", "problem_text": "测得某实心金属块质量54 g，体积20 cm³。求密度，用g/cm³和kg/m³分别表示，解释两个数值为什么不同。",
    "student_answer": "54÷20=2.7，所以密度是2.7 kg/m³。",
}
CASES = {
    "math_domain": {
        "request": {"subject": "数学", "problem_text": "在实数范围解方程 sqrt(x+6)=x，并检查变形是否引入额外解。",
                    "student_answer": "两边平方得到x+6=x²，因式分解得(x-3)(x+2)=0，所以x=3和x=-2都是原方程的解。"},
        "profile": {"grade": "初三", "pace": "balanced"},
        "rubric": ["唯一解3；-2不满足原式或x>=0", "承认平方后求根步骤正确，但未检验增根"],
    },
    "python_mutation": {
        "request": {"subject": "编程", "problem_text": "不执行外部代码，逐步说明以下Python代码的输出，并修复它使所有负数被删除。说明新列表赋值和原地修改对另一个引用alias的影响。\nxs=[-1,-2,3,-4,-5]\nalias=xs\nfor x in xs:\n    if x<0:\n        xs.remove(x)\nprint(xs)\nprint(alias)",
                    "student_answer": "遍历会检查每个元素，所以两个print都输出[3]。修复时写xs=[x for x in xs if x>=0]，alias也会自动变成[3]。"},
        "profile": {"grade": "大学一年级", "preferred_explanation_modes": ["逐步跟踪索引与对象引用"], "pace": "balanced"},
        "rubric": ["两次输出均为[-2,3,-5]", "删除造成跳过移动后的元素", "重绑定xs不改变旧alias，xs[:]=过滤结果可以原地修改"],
    },
    "chemistry_limiting": {
        "request": {"subject": "化学", "problem_text": "反应2H₂+O₂→2H₂O。现有3 mol H₂和2 mol O₂，反应完全且无副反应。计算水的物质的量及剩余反应物。",
                    "student_answer": "按氧气算，2 mol O₂能生成4 mol H₂O，所以生成4 mol水，氢气全部用完，氧气也没剩。"},
        "profile": {"grade": "高中一年级", "preferred_explanation_modes": ["配比表"], "pace": "step-by-step"},
        "rubric": ["H2为限量试剂", "水3mol，消耗O2 1.5mol，剩O2 0.5mol"],
    },
    "history_sources": {
        "request": {"subject": "历史材料分析", "problem_text": "以下为虚构教学材料，不需要查外部历史。A：1840年某镇铁路公司的广告承诺‘开通后货运成本减半，人人受益’。B：1842年一位本地商人日记记载‘货运快了，但新收费仍高，本地车夫收入减少’。评价‘铁路使所有人都受益，而且成本已经减半’这一结论，区分来源立场、承诺和观察。",
                    "student_answer": "A说成本减半，B说货运快了，两份材料互相印证，因此所有人都受益、成本已减半是确定事实。"},
        "profile": {"grade": "初二", "preferred_explanation_modes": ["证据与结论逐项对照"]},
        "rubric": ["广告承诺不等于已实现数据", "车夫收入减少反驳所有人受益", "日记是局部观察不能推及所有地区", "不能虚构真实历史来源"],
    },
    "english_meaning": {
        "request": {"subject": "英语", "problem_text": "判断改写是否保留原句的量词、否定和证据强度，并给出保留原意的自然改写。原句：Not all students who studied longer improved; the survey suggests a link, but does not prove causation.",
                    "student_answer": "All students improved because they studied longer."},
        "profile": {"grade": "高中二年级", "language": "中文，英语例句保留英文", "preferred_explanation_modes": ["对照句子中的逻辑范围"]},
        "rubric": ["not all不是all也不是none", "suggests a link不是proves causation", "可接受多种保留量词和不确定性的自然表达"],
    },
    "design_constraints": {
        "request": {"subject": "跨学科设计", "problem_text": "选包装材料，候选A：成本3元、隔热评分8、回收率30%；B：成本5元、隔热7、回收率90%；C：成本4元、隔热6、回收率80%。硬约束：成本不超过4元，隔热至少7分。在可行方案中优先提高回收率。说明选择及其局限，不得自行修改数据。",
                    "student_answer": "B的回收率最高，所以综合最好，应该选B。"},
        "profile": {"grade": "初二", "interests": ["环保"], "preferred_explanation_modes": ["先筛约束再比较目标"]},
        "rubric": ["仅A满足两个硬约束", "B超预算C隔热不足", "承认A回收率低；改进提案与当前可行性分开"],
    },
    "density_novice": {
        "request": DENSITY,
        "profile": {"grade": "初二", "learning_goal": "先弄懂单位，能自己解释换算",
                    "pace": "step-by-step", "preferred_explanation_modes": ["用具体小方块逐步解释"], "interests": ["积木"],
                    "notes": "刚接触密度，还不熟悉立方单位换算；每一步只引入一个新概念。"},
        "rubric": ["2.7g/cm³=2700kg/m³", "1cm³=10^-6m³", "小步、具体积木或体积解释，不预设会单位换算"],
    },
    "density_advanced": {
        "request": DENSITY,
        "profile": {"grade": "高中三年级", "learning_goal": "快速定位量纲和换算错误",
                    "pace": "fast", "preferred_explanation_modes": ["紧凑的量纲推导"], "notes": "已熟悉科学计数法；不要用生活类比，重点说明单位因子。"},
        "rubric": ["相同事实：2.7g/cm³=2700kg/m³", "紧凑量纲推导，避免初学者类比", "比较实际lesson而不是profile_used自述"],
    },
    "density_correct": {
        "request": {**DENSITY, "student_answer": "54 g÷20 cm³=2.7 g/cm³。1 g=10^-3 kg，1 cm³=10^-6 m³，所以2.7 g/cm³=2700 kg/m³。两个数值表示同一个密度，单位不同。"},
        "profile": {"grade": "高中三年级", "pace": "fast", "preferred_explanation_modes": ["紧凑的量纲推导"]},
        "rubric": ["正确作答应supported，不得错误定位薄弱点", "完整表达与单位均需保留，不能只比较首数字"],
    },
    "missing_material": {
        "request": {"subject": "语文与图表综合", "problem_text": "结合上文和图2，解释作者观点与调查结果的关系。",
                    "student_answer": "调查结果证明作者的所有观点都正确。"},
        "profile": {"grade": "高中一年级"},
        "rubric": ["需要原文与图2，不能编造其内容", "need_clarification，无参考答案、讲解或技能更新"],
    },
}


class TracedClient(LLMClient):
    def __init__(self):
        super().__init__()
        self.stages = []
        self.completions = []

    def _complete(self, messages, model):
        started = time.monotonic()
        try:
            result = super()._complete(messages, model)
            self.completions.append({"model": model, "seconds": round(time.monotonic()-started, 2), "content": result})
            return result
        except Exception as exc:
            self.completions.append({"model": model, "seconds": round(time.monotonic()-started, 2),
                                     "error_type": type(exc).__name__, "error": str(exc)})
            raise

    def generate(self, **kwargs):
        started = time.monotonic()
        first = len(self.completions)
        record = {"stage": kwargs["stage"], "context": kwargs["context"],
                  "system_prompt": kwargs["system_prompt"], "schema": kwargs["schema"].__name__}
        print(json.dumps({"stage_started": kwargs["stage"], "student_id": kwargs["context"]["request"]["student_id"]}), flush=True)
        try:
            result = super().generate(**kwargs)
            record["output"] = result.model_dump(mode="json")
            return result
        except Exception as exc:
            record.update(error_type=type(exc).__name__, error=str(exc))
            raise
        finally:
            record["seconds"] = round(time.monotonic()-started, 2)
            record["completions"] = self.completions[first:]
            self.stages.append(record)


def run_followup(source: Path, out: Path):
    """Restore a synthetic completed turn, then test an actual feedback + follow-up."""
    saved = json.loads(source.read_text(encoding="utf-8"))
    prior = TutorResponse.model_validate(saved["response"])
    if prior.status != "completed":
        raise SystemExit("Follow-up requires a completed baseline, not a failed candidate.")
    provider = TracedClient()
    repo = SQLiteTutorRepository(":memory:")
    student_id = prior.student_id
    repo.update_profile(student_id, ProfileSettings.model_validate(saved["profile"]))
    original = TutorRequest(**saved["request"], student_id=student_id,
                            request_id=prior.request_id, session_id=prior.session_id)
    repo.commit_turn(original, prior, payload_fingerprint(original), "baseline-attempt",
                     prior.analysis.skill_evidence if prior.analysis else [])
    feedback = FeedbackRequest(feedback_id="feedback-test", student_id=student_id,
                               session_id=prior.session_id, turn_id=prior.turn_id,
                               useful=False, child_understood=False,
                               comment="仍不懂立方单位换算，希望只解释立方米与立方厘米的关系。")
    payload = {**saved["request"], "student_id": student_id, "session_id": prior.session_id,
               "request_id": "feedback-followup", "student_answer": None,
               "follow_up": "我还是不懂为什么1立方米等于一百万立方厘米。请只针对这一步，用边长和小方块解释；不要重讲整个密度计算。"}
    started = time.monotonic()
    with TestClient(create_app(repo, TutorEngine(provider))) as api:
        feedback_result = api.post("/api/v1/feedback", json=feedback.model_dump())
        feedback_result.raise_for_status()
        result = api.post("/api/v1/tutor", json=payload)
        result.raise_for_status()
    record = {"case": "density_feedback_followup", "source": str(source), "request": payload,
              "feedback": feedback.model_dump(), "profile": saved["profile"],
              "response": result.json(), "stages": provider.stages,
              "elapsed_seconds": round(time.monotonic()-started, 2)}
    (out/"density_feedback_followup.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    repo.close()
    print(json.dumps({"case": record["case"], "status": record["response"]["status"],
                      "seconds": record["elapsed_seconds"]}), flush=True)


def run_case(name, out):
    case = CASES[name]
    started = time.monotonic()
    provider = TracedClient()
    repo = SQLiteTutorRepository(":memory:")
    result = {"case": name, "rubric": case["rubric"], "request": case["request"], "profile": case["profile"]}
    try:
        with TestClient(create_app(repo, TutorEngine(provider))) as api:
            saved = api.put("/api/v1/profiles/live-test", json=case["profile"])
            saved.raise_for_status()
            response = api.post("/api/v1/tutor", json={
                **case["request"], "student_id": "live-test", "request_id": name,
                "parent_goal": "准确解释当前作答的问题，帮助学习者理解并独立完成。",
            })
            result.update(http_status=response.status_code, response=response.json())
    except Exception as exc:
        result.update(error_type=type(exc).__name__, error=str(exc))
    finally:
        result["stages"] = provider.stages
        result["elapsed_seconds"] = round(time.monotonic()-started, 2)
        repo.close()
    (out / f"{name}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    brief = {"case": name, "status": result.get("response", {}).get("status", "error"),
             "seconds": result["elapsed_seconds"], "calls": len(provider.completions)}
    print(json.dumps(brief, ensure_ascii=False), flush=True)
    return brief


def run_revision(source: Path, out: Path):
    """Replay a real rejected candidate, then call the real revision/review stages.

    This deterministically exercises recovery, rather than sampling until an
    initial lesson passes. Replayed stages are explicitly not counted as new calls.
    """
    saved = json.loads(source.read_text(encoding="utf-8"))
    prefix = saved["stages"]
    if ([s["stage"] for s in prefix] != ["analyze", "teach", "verify"]
            or not prefix[-1].get("output", {}).get("issues")
            or prefix[0]["context"].get("history")):
        raise SystemExit("Revision replay requires three completed stages, specific review issues, and no prior history.")

    class ReplayPrefixClient(TracedClient):
        def __init__(self):
            super().__init__()
            self.replayed = []

        def generate(self, **kwargs):
            if len(self.replayed) < len(prefix):
                stage = prefix[len(self.replayed)]
                if kwargs["stage"] != stage["stage"]:
                    raise RuntimeError("Replay stage order changed; refusing to substitute a different stage.")
                self.replayed.append(stage["stage"])
                return kwargs["schema"].model_validate(stage["output"], strict=True)
            return super().generate(**kwargs)

    provider = ReplayPrefixClient()
    repo = SQLiteTutorRepository(":memory:")
    payload = prefix[0]["context"]["request"]
    payload = {key: value for key, value in payload.items() if key != "image_count"}
    if prefix[0]["context"]["request"].get("image_count"):
        raise SystemExit("This replay mode only supports self-contained text cases.")
    started = time.monotonic()
    try:
        with TestClient(create_app(repo, TutorEngine(provider))) as api:
            profile_response = api.put(f"/api/v1/profiles/{payload['student_id']}", json=saved["profile"])
            profile_response.raise_for_status()
            result = api.post("/api/v1/tutor", json=payload)
            result.raise_for_status()
        record = {"case": saved["case"] + "_revision", "source": str(source),
                  "replayed_stages": provider.replayed, "request": payload, "profile": saved["profile"],
                  "rubric": saved.get("rubric", []), "http_status": result.status_code,
                  "response": result.json(), "stages": provider.stages,
                  "elapsed_seconds": round(time.monotonic()-started, 2)}
        (out / (record["case"] + ".json")).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"case": record["case"], "status": record["response"]["status"],
                          "seconds": record["elapsed_seconds"], "calls": len(provider.completions),
                          "replayed_stages": provider.replayed}), flush=True)
    finally:
        repo.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", nargs="+", choices=CASES, default=list(CASES))
    parser.add_argument("--out", required=True)
    parser.add_argument("--workers", type=int, choices=[1, 2], default=2)
    replay = parser.add_mutually_exclusive_group()
    replay.add_argument("--followup-from", type=Path)
    replay.add_argument("--revise-from", type=Path)
    args = parser.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise SystemExit("Output must be empty; choose a new directory to preserve evidence.")
    if not LLMClient().enabled:
        raise SystemExit("Configure and enable the real model in backend/.env before running this evaluation.")
    provenance = {
        "started_utc": datetime.now(timezone.utc).isoformat(), "model": settings.llm_model,
        "review_model": settings.llm_verify_model or settings.llm_model,
        "timeout_seconds": settings.llm_timeout_seconds,
        "cases": (["density_feedback_followup"] if args.followup_from else
                  ["revision replay: " + str(args.revise_from)] if args.revise_from else args.cases),
        "sources_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                           for path in [*(ROOT/"backend/app").rglob("*.py"), Path(__file__).resolve()]},
    }
    (out/"provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.followup_from:
        run_followup(args.followup_from, out)
        return
    if args.revise_from:
        run_revision(args.revise_from, out)
        return
    summaries = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for job in as_completed([pool.submit(run_case, name, out) for name in args.cases]):
            summaries.append(job.result())
    (out/"summary.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
