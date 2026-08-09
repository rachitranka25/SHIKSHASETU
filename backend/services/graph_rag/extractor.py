import json
import logging
from typing import List

from .graph_store import get_graph_store

logger = logging.getLogger(__name__)

class GraphExtractor:
    """
    Extracts Entities and Relationships from unstructured text
    and populates the Knowledge Graph.
    """

    def __init__(self, inference_engine=None):
        self.graph_store = get_graph_store()
        
        # If not provided, we lazy load the InferenceEngine
        self._inference_engine = inference_engine
        
    @property
    def engine(self):
        if not self._inference_engine:
            from ..inference import get_inference_engine
            self._inference_engine = get_inference_engine()
        return self._inference_engine

    async def extract_and_store(self, text: str, source_metadata: dict = None) -> None:
        """
        Uses the LLM to extract entities and relationships, then stores them in NetworkX.
        """
        if not text or len(text) < 20:
            return

        prompt = f"""You are an advanced Knowledge Graph extractor.
Given the following educational text, extract key entities and the relationships between them.

Format your response exactly as a JSON object with this structure:
{{
  "entities": [
    {{"name": "Mitochondria", "type": "Organelle"}},
    {{"name": "Cell", "type": "Biological Unit"}}
  ],
  "relationships": [
    {{"source": "Mitochondria", "target": "Cell", "type": "part of"}}
  ]
}}

Text:
{text}

Output JSON only. Do not include markdown blocks.
"""
        try:
            # We use generation without streaming
            from ...core.model_config import GenerationConfig
            config = GenerationConfig(temperature=0.1, max_tokens=1000)
            
            response = await self.engine.generate(prompt, config)
            # Parse JSON out of response
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
                
            data = json.loads(response.strip())
            
            entities = data.get("entities", [])
            relationships = data.get("relationships", [])
            
            # Store entities
            for ent in entities:
                self.graph_store.add_entity(ent["name"], ent.get("type", "unknown"), source_metadata)
                
            # Store relationships
            for rel in relationships:
                self.graph_store.add_relationship(rel["source"], rel["target"], rel.get("type", "related to"))
                
            # Persist graph
            self.graph_store.save_graph()
            logger.info(f"GraphRAG Extraction successful: added {len(entities)} entities, {len(relationships)} relationships.")
            
        except Exception as e:
            logger.error(f"Failed to extract knowledge graph: {e}")

