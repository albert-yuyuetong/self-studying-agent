# Architecture Scaffold

This document maps the conceptual design in the root README to the current code scaffold.

## Layers

1. Parent Interaction Layer
- Current status: placeholder in frontend folder.
- Future: mini-program/web app for photo upload, voice, and feedback.

2. Agent Orchestration Layer
- Implemented at app/orchestration/tutor_orchestrator.py.
- Responsibility: intent routing, LLM-based question typing, reference-answer gating, service composition, and profile-aware output strategy.

3. Domain Service Layer
- app/services/problem_analysis_service.py
- app/services/problem_parser.py
- app/services/grading_service.py
- app/services/style_adapter.py
- app/services/explanation_generator.py
- app/services/practice_generator.py
- app/services/llm_client.py

4. Data and Profile Layer
- app/repositories/profile_repository.py provides in-memory profile persistence.
- app/profile/bkt.py provides lightweight BKT probability update.

## MVP Flow Implemented

1. POST /api/v1/diagnose receives one problem request.
2. LLM-first problem analysis classifies the question as standard-answer or open-ended.
3. For standard-answer questions, the system tries to obtain an LLM-derived reference answer before grading.
4. Parse problem and infer target knowledge points.
5. Standard-answer questions with a reference answer go through grading and error classification; open-ended questions skip grading.
6. Select explanation style based on profile and feedback.
7. Update mastery using BKT only when a standard-answer question has been graded.
8. Return parent coaching card, guiding questions, and practice suggestion.

## Next Build Targets

1. OCR and multimodal ingestion.
2. Knowledge graph backed concept taxonomy.
3. PostgreSQL + Redis integration.
4. LLM strategy layer for richer parent coaching scripts.
5. Stronger reference-answer generation for standard-answer questions.
