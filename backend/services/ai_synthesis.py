import os
import json
import logging
from groq import Groq

logger = logging.getLogger(__name__)

client = Groq()

class StandupGenerator:
    @staticmethod
    def generate(metrics_payload: dict) -> str:
        """
        Feeds deterministic database metrics into Llama 3 70B to generate an engineering standup.
        """
        system_prompt = (
            "You are an elite Engineering Manager. Your goal is to write a concise, highly actionable "
            "daily standup summary based on the provided developer metrics. \n"
            "Rules:\n"
            "1. Focus strictly on blockages (Stale PRs), momentum (Commit Velocity), and review delays (Merge Lag).\n"
            "2. Do not use greetings, pleasantries, or robotic transitions (e.g., 'Here is your summary').\n"
            "3. Use a direct, professional tone. Format with clear bullet points.\n"
            "4. If a metric looks bad (e.g., a PR open for 72+ hours), call it out as a high-priority blocker."
        )

        try:
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user", 
                        "content": f"Generate a standup based on this current state:\n{json.dumps(metrics_payload, indent=2)}"
                    }
                ],
                model="llama3-70b-8192",
                temperature=0.3, 
                max_tokens=600
            )
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Groq API generation failed: {e}")
            return "Failed to generate standup summary due to an upstream AI provider error."