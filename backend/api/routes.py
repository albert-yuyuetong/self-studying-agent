from fastapi import APIRouter

from backend.models import DiagnoseRequest, DiagnoseResponse
from backend.services.pipeline import TutorWorkflow

router = APIRouter(prefix="/api/v1", tags=["agent"])
workflow = TutorWorkflow()


@router.get("/framework")
def framework_overview() -> dict[str, object]:
    return {
        "product_focus": "面向家长的辅导助手，而不是直接给孩子答案",
        "layers": [
            {
                "name": "interaction",
                "responsibility": "接收家长输入并返回可执行的辅导建议",
            },
            {
                "name": "orchestration",
                "responsibility": "协调画像、诊断与讲解生成流程",
            },
            {
                "name": "domain_services",
                "responsibility": "题目诊断、画像推断、讲解卡片生成",
            },
            {
                "name": "data_and_profile",
                "responsibility": "沉淀学生画像与后续评估数据",
            },
        ],
        "modules": {
            "backend": "FastAPI 服务与最小 Agent 编排骨架",
            "docs": "产品方案、画像设计与知识图谱文档",
            "frontend": "家长端前端占位目录",
            "evaluation": "效果评估与离线验证占位目录",
        },
    }


@router.post("/diagnoses", response_model=DiagnoseResponse)
def diagnose(request: DiagnoseRequest) -> DiagnoseResponse:
    return workflow.run(request)
