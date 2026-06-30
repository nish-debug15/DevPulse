import os
import json
import logging
from groq import Groq
from pydantic import BaseModel, Field, ValidationError
from typing import List

logger = logging.getLogger(__name__)

class ActionItem(BaseModel):
    pr_number: int = Field(description="The GitHub Pull Request number")
    owner: str = Field(description="The username of the PR owner")
    issue: str = Field(description="The specific bottleneck, e.g., 'High Code Churn (15 commits)', 'Stale (72h)'")
    action: str = Field(description="Direct 1-2 sentence instruction on who to ping and what to do")

class StandupSynthesis(BaseModel):
    synthesis_summary: str = Field(description="A 2-3 sentence overarching summary of the team's momentum and blockers")
    action_items: List[ActionItem] = Field(description="List of specific action items to unblock the team")

class StandupGenerator:
    _client = None

    @classmethod
    def _get_client(cls) -> Groq:
        """
        Lazy instantiation implementation for the external SDK client.
        Ensures runtime hydration of environment variables before client configuration.
        """
        if cls._client is None:
            if not os.getenv("GROQ_API_KEY"):
                logger.critical("Initialization failure: GROQ_API_KEY environment variable is missing.")
                raise RuntimeError("GROQ_API_KEY environment variable is missing.")
            cls._client = Groq()
        return cls._client

    @classmethod
    def generate(cls, metrics_payload: dict) -> dict:
        """
        Feeds deterministic database metrics into Qwen 3.6 27B.
        Returns a validated dictionary matching the StandupSynthesis schema.
        """
        schema_json = StandupSynthesis.model_json_schema()
        
        system_prompt = (
            "You are an elite, direct Engineering Manager. Analyze the developer metrics and output actionable intelligence.\n"
            "Rules:\n"
            "1. Focus strictly on Stale PRs (Merge Lag > 48h) and Code Churn (e.g., >10 commits on unmerged PRs).\n"
            "2. Generate precise Action Items detailing exactly who to ping and what to do to unblock the pipeline.\n"
            "3. No pleasantries. No Markdown formatting outside of the JSON block.\n"
            "4. You MUST output ONLY valid JSON that strictly adheres to the following schema:\n"
            f"{json.dumps(schema_json, indent=2)}"
        )

        try:
            groq_client = cls._get_client()
            
            response = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user", 
                        "content": f"Generate actionable JSON based on this current state:\n{json.dumps(metrics_payload, indent=2)}"
                    }
                ],
                model="qwen-3.6-27b",
                temperature=0.1, 
                max_tokens=800,
                response_format={"type": "json_object"} 
            )
            
            raw_content = response.choices[0].message.content
            parsed_json = json.loads(raw_content)
            
            validated_data = StandupSynthesis(**parsed_json)
            
            return validated_data.model_dump()
            
        except json.JSONDecodeError as e:
            logger.error(f"LLM failed to return valid JSON: {e}. Raw output: {raw_content}")
            return cls._fallback_response()
        except ValidationError as e:
            logger.error(f"LLM output violated schema: {e}")
            return cls._fallback_response()
        except Exception as e:
            logger.error(f"Groq API generation failed: {e}")
            return cls._fallback_response()

    @classmethod
    def _fallback_response(cls) -> dict:
        """Production fallback to prevent UI crashes if the LLM hallucinates or the API drops."""
        return {
            "synthesis_summary": "Data ingestion complete, but AI synthesis is currently degraded. Please review metrics manually.",
            "action_items": []
        }