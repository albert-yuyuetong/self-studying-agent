# Architecture Scaffold

This document maps the conceptual design in the root README to the current code scaffold.

## Layers

1. Parent Interaction Layer
- Current status: placeholder in frontend folder.
- Future: mini-program/web app for photo upload, voice, and feedback.

2. Agent Orchestration Layer
- Implemented at app/orchestration/tutor_orchestrator.py.
- Responsibility: intent routing, service composition, and profile-aware output strategy.

3. Domain Service Layer
- app/services/problem_parser.py
- app/services/grading_service.py
- app/services/style_adapter.py
- app/services/explanation_generator.py
- app/services/practice_generator.py

4. Data and Profile Layer
- app/repositories/profile_repository.py provides in-memory profile persistence.
- app/profile/bkt.py provides lightweight BKT probability update.

## MVP Flow Implemented

1. POST /api/v1/diagnose receives one problem request.
2. Parse problem and infer target knowledge points.
3. Grade student answer and classify high-level error type.
4. Select explanation style based on profile and feedback.
5. Update mastery using BKT and save profile.
6. Return parent coaching card, guiding questions, and practice suggestion.

## Next Build Targets

1. OCR and multimodal ingestion.
2. Knowledge graph backed concept taxonomy.
3. PostgreSQL + Redis integration.
4. LLM strategy layer for richer parent coaching scripts.
