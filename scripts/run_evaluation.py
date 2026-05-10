"""
Evaluation runner using DeepEval.

Usage:
    python scripts/run_evaluation.py [--category RAG] [--output evaluation/reports]

Metrics evaluated:
    - AnswerRelevancyMetric   : Is the response on-topic?
    - FaithfulnessMetric      : Does the answer stay within retrieved context?
    - ContextualRecallMetric  : Did retrieval capture necessary information?
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("evaluation")


def load_test_cases(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run DeepEval evaluation for TechGear Agent")
    parser.add_argument(
        "--test-cases",
        default="evaluation/test_cases.json",
        help="Path to test cases JSON file",
    )
    parser.add_argument(
        "--category",
        choices=["RAG", "Order", "Edge", "all"],
        default="all",
        help="Filter by test case category (default: all)",
    )
    parser.add_argument(
        "--output",
        default="evaluation/reports",
        help="Output directory for HTML reports",
    )
    return parser.parse_args()


def build_deepeval_test_cases(
    raw_cases: list[dict],
    category: str,
) -> list:
    """Convert raw JSON test cases into DeepEval LLMTestCase objects."""
    from deepeval.test_case import LLMTestCase

    from src.agent.agent import invoke_agent
    from src.rag.retriever import get_retriever

    retriever = get_retriever()
    deepeval_cases = []

    for tc in raw_cases:
        if category != "all" and tc.get("category") != category:
            continue

        logger.info("Running test case: %s — '%s'", tc["id"], tc["input"][:60])

        # Get actual response from the agent (new session per test case for isolation)
        actual_output = invoke_agent(
            user_message=tc["input"],
            session_id=f"eval_{tc['id']}",
        )

        # Get actual retrieval context (only for RAG cases)
        retrieval_context: list[str] = []
        if tc.get("category") == "RAG":
            results = retriever.retrieve(tc["input"])
            retrieval_context = [r.content for r in results]

        case = LLMTestCase(
            input=tc["input"],
            actual_output=actual_output,
            expected_output=tc.get("expected_output", ""),
            retrieval_context=retrieval_context if retrieval_context else None,
            context=retrieval_context if retrieval_context else None,
        )
        deepeval_cases.append(case)

    return deepeval_cases


def run_evaluation(args: argparse.Namespace) -> None:
    from deepeval import evaluate
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        ContextualRecallMetric,
        FaithfulnessMetric,
    )

    from src.config import get_settings

    settings = get_settings()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_cases = load_test_cases(Path(args.test_cases))
    logger.info("Loaded %d test cases from %s", len(raw_cases), args.test_cases)

    logger.info("Building test cases (invoking agent for each)...")
    test_cases = build_deepeval_test_cases(raw_cases, category=args.category)
    logger.info("Prepared %d DeepEval test cases.", len(test_cases))

    # Use GoogleVertexAI-compatible wrapper via langchain_google_genai
    import os
    os.environ["GOOGLE_API_KEY"] = settings.gemini_api_key

    from deepeval.models.base_model import DeepEvalBaseLLM
    from langchain_google_genai import ChatGoogleGenerativeAI

    class GeminiEvalModel(DeepEvalBaseLLM):
        def __init__(self, model_name: str, api_key: str):
            self.model_name = model_name
            self.api_key = api_key

        def load_model(self):
            return ChatGoogleGenerativeAI(
                model=self.model_name,
                google_api_key=self.api_key,
                temperature=0,
            )

        def generate(self, prompt: str) -> str:
            model = self.load_model()
            res = model.invoke(prompt)
            return res.content

        async def a_generate(self, prompt: str) -> str:
            model = self.load_model()
            res = await model.ainvoke(prompt)
            return res.content

        def get_model_name(self) -> str:
            return self.model_name

    eval_model = GeminiEvalModel(
        model_name=settings.llm_model,
        api_key=settings.gemini_api_key,
    )

    metrics = [
        AnswerRelevancyMetric(
            threshold=0.7,
            model=eval_model,
            include_reason=True,
        ),
        FaithfulnessMetric(
            threshold=0.7,
            model=eval_model,
            include_reason=True,
        ),
        ContextualRecallMetric(
            threshold=0.7,
            model=eval_model,
            include_reason=True,
        ),
    ]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = output_dir / f"eval_report_{timestamp}.html"

    logger.info("Running DeepEval evaluation...")
    results = evaluate(
        test_cases=test_cases,
        metrics=metrics,
        run_async=False,
        show_indicator=True,
    )

    # Save a simple JSON report (deepeval 2.x returns list of TestResult objects)
    import json as _json

    report_data = []
    for item in (results if isinstance(results, (list, tuple)) else [results]):
        # In deepeval 2.x, evaluate() may return tuples or TestResult objects
        if isinstance(item, tuple):
            tc, item_metrics = item[0], item[1] if len(item) > 1 else []
            report_data.append({
                "input": getattr(tc, "input", str(tc)),
                "actual_output": getattr(tc, "actual_output", ""),
                "success": all(getattr(m, "success", True) for m in item_metrics),
                "metrics_data": [
                    {
                        "name": getattr(m, "name", str(m)),
                        "score": getattr(m, "score", None),
                        "passed": getattr(m, "success", None),
                        "reason": getattr(m, "reason", ""),
                    }
                    for m in item_metrics
                ],
            })
        else:
            report_data.append({
                "input": getattr(item, "input", str(item)),
                "actual_output": getattr(item, "actual_output", ""),
                "success": getattr(item, "success", None),
                "metrics_data": [
                    {
                        "name": getattr(m, "name", str(m)),
                        "score": getattr(m, "score", None),
                        "passed": getattr(m, "success", None),
                        "reason": getattr(m, "reason", ""),
                    }
                    for m in getattr(item, "metrics_data", [])
                ],
            })

    report_json = output_dir / f"eval_report_{timestamp}.json"
    report_json.write_text(_json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("✅ Evaluation complete! Report saved to: %s", report_json)


if __name__ == "__main__":
    args = parse_args()
    run_evaluation(args)
