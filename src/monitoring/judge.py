"""
LLM-based response quality assessment.
"""

import json
from openai import OpenAI
from typing import Optional
from src.monitoring.metrics import LLMRelevanceScore


class ResponseJudge:
    """Judges response quality using LLM."""

    ASSESSMENT_PROMPT = """You are evaluating the quality of an AI assistant's response to a user query.

User Query: {query}

Assistant Response: {response}

Evaluate how well the response addresses the user's query. Consider:
1. Did it answer what was asked?
2. Is the information accurate and relevant?
3. Is it complete and helpful?

Provide your assessment in JSON format:
{{
    "score": "EXCELLENT" | "ADEQUATE" | "POOR",
    "reasoning": "Brief explanation of your assessment (1-2 sentences)"
}}

Score definitions:
- EXCELLENT: Fully addresses the query with comprehensive, relevant information
- ADEQUATE: Addresses the query but could be more complete or relevant
- POOR: Does not adequately address the query or contains irrelevant information"""

    def __init__(self, openai_client: OpenAI):
        self.client = openai_client

    def assess_response(
        self, query: str, response: str
    ) -> tuple[LLMRelevanceScore, Optional[str]]:
        """
        Assess response quality using LLM.

        Returns:
            (score, reasoning)
        """
        try:
            assessment_result = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an objective evaluator of AI responses.",
                    },
                    {
                        "role": "user",
                        "content": self.ASSESSMENT_PROMPT.format(
                            query=query, response=response
                        ),
                    },
                ],
                temperature=0.3,
                response_format={"type": "json_object"},
            )

            result_text = assessment_result.choices[0].message.content
            result = json.loads(result_text)

            score_str = result.get("score", "NOT_JUDGED").upper()
            reasoning = result.get("reasoning", "")

            # Map string to enum
            score_map = {
                "EXCELLENT": LLMRelevanceScore.EXCELLENT,
                "ADEQUATE": LLMRelevanceScore.ADEQUATE,
                "POOR": LLMRelevanceScore.POOR,
            }

            score = score_map.get(score_str, LLMRelevanceScore.NOT_JUDGED)

            return score, reasoning

        except Exception as e:
            print(f"[ERROR] Failed to assess response: {e}")
            return LLMRelevanceScore.NOT_JUDGED, f"Assessment failed: {str(e)}"
