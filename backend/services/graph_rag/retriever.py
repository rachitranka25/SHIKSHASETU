import logging
from typing import List

from .graph_store import get_graph_store

logger = logging.getLogger(__name__)

class GraphRetriever:
    """
    Retrieves subgraphs from the Knowledge Graph based on a query.
    Used to augment prompts with semantic relationships.
    """

    def __init__(self, inference_engine=None):
        self.graph_store = get_graph_store()
        self._inference_engine = inference_engine
        
    @property
    def engine(self):
        if not self._inference_engine:
            from ..inference import get_inference_engine
            self._inference_engine = get_inference_engine()
        return self._inference_engine

    async def retrieve_context(self, query: str, depth: int = 2) -> str:
        """
        Retrieves context from the Knowledge Graph for the given query.
        """
        # 1. Extract entities from the query
        entities = await self._extract_entities_from_query(query)
        if not entities:
            return ""
            
        # 2. Get the subgraph context from the graph store
        context = self.graph_store.get_subgraph_context(entities, depth=depth)
        
        if context:
            logger.info(f"GraphRAG retrieved context for entities: {entities}")
        
        return context

    async def _extract_entities_from_query(self, query: str) -> List[str]:
        """
        Uses a fast LLM call to extract the main entities from the user's question.
        """
        prompt = f"""Identify the core educational entities (nouns, concepts) in this question.
Return them as a comma-separated list. No other text.

Question: {query}
Entities:"""

        try:
            from ...core.model_config import GenerationConfig
            config = GenerationConfig(temperature=0.1, max_tokens=50)
            
            response = await self.engine.generate(prompt, config)
            # Parse comma separated list
            entities = [e.strip() for e in response.split(",") if e.strip()]
            return entities
        except Exception as e:
            logger.error(f"Failed to extract entities from query: {e}")
            return []

