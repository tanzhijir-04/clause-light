# Task 8 Report: Feedback-to-Knowledge Pipeline

## Status: DONE

## Summary

Implemented the feedback-to-knowledge auto-learning pipeline. When a user submits "incorrect" feedback on a clause analysis, the system now automatically creates a new knowledge rule from the clause content, entering it into the pending-review queue for administrator approval.

## Changes Made

### `server/core/knowledge.py`

- Added `trigger_auto_learning(clause)` method to `KnowledgeEngine` class
  - Extracts clause content and creates a new KnowledgeRule with `source="auto_learned"` and `confidence=0.6`
  - Deduplicates by checking if an identical rule already exists
  - Maps clause `risk_type` to rule category via `TYPE_CATEGORY_MAP`
  - Extracts keywords from clause text for rule matching

- Added `_extract_keywords(text, max_keywords)` helper function
  - Splits clause text on Chinese punctuation
  - Filters fragments by length (3-20 chars)
  - Returns up to 5 keywords for rule trigger matching

### `server/api/contracts.py`

- Modified `submit_feedback` endpoint to:
  - Call `KnowledgeEngine.trigger_auto_learning(clause)` when `feedback == "incorrect"`
  - Added `await db.commit()` (was missing in original code)
  - Returns `autoLearned` boolean in response to indicate if a new rule was created

## Pipeline Flow

1. User submits feedback with `feedback=incorrect` on a clause analysis
2. Feedback is saved to `ClauseAnalysis.user_feedback`
3. `KnowledgeEngine.trigger_auto_learning()` is invoked
4. Engine checks for duplicate rules (same `rule_text`)
5. If no duplicate, creates a new `KnowledgeRule` with:
   - `source = "auto_learned"`
   - `confidence = 0.6`
   - `category` mapped from clause's `risk_type`
   - `trigger_keywords` extracted from clause text
6. Rule enters the pending-review queue (visible in admin dashboard)
7. Administrator can approve (`confidence += 0.2`, `source -> "manual"`) or reject (`is_active = False`)

## Test Results

All 38 existing tests pass (no regressions):
- `tests/test_api_contracts.py`: 11/11 passed
- `tests/test_knowledge.py`: 27/27 passed
