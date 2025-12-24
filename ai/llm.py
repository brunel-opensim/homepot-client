import logging
from typing import Any, Dict, List, Optional

import ollama
import yaml

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LLMService:
    """Service for interacting with local LLM via Ollama."""

    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
        
        self.model = self.config["llm"]["model"]
        self.base_url = self.config["llm"]["base_url"]
        
        # Initialize Ollama client
        self.client = ollama.Client(host=self.base_url)
        logger.info(f"LLM Service initialized with model: {self.model}")

    def generate_response(self, prompt: str, context: Optional[str] = None) -> str:
        """Generate a response from the LLM."""
        try:
            full_prompt = prompt
            if context:
                full_prompt = f"Context:\n{context}\n\nQuestion: {prompt}"
            
            response = self.client.generate(
                model=self.model,
                prompt=full_prompt,
                options={
                    "temperature": self.config["llm"]["temperature"]
                }
            )
            return response["response"]
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return "I apologize, but I encountered an error processing your request."

    def check_health(self) -> bool:
        """Check if Ollama is reachable."""
        try:
            self.client.list()
            return True
        except Exception:
            return False
