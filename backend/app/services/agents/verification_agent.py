"""
Verification Agent - Validates RAG results and refines searches

This agent improves RAG quality by:
1. Checking if retrieved chunks actually answer the query
2. Detecting missing information
3. Reformulating and re-searching if needed
4. Iterative refinement (max 3 iterations)

Use Cases:
- Low confidence results → try different query formulation
- Incomplete answers → search for missing pieces
- Wrong document → refine search terms

Architecture:
- Input: query + retrieved chunks
- Output: verified/refined chunks
- Integration: Plugs into RAGService.search() with use_verification flag

IMPORTANT: This is a NON-BREAKING enhancement
- Default: DISABLED (use_verification=False)
- When enabled: Returns same format as normal search
- Compatible with existing pipeline
"""

import structlog
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from enum import Enum

from app.services.llm_service import LLMService

logger = structlog.get_logger()


class VerificationStatus(str, Enum):
    """Status of verification"""
    COMPLETE = "complete"  # Answer is complete
    INCOMPLETE = "incomplete"  # Answer missing key information
    WRONG_FOCUS = "wrong_focus"  # Retrieved wrong document/topic
    LOW_CONFIDENCE = "low_confidence"  # Low scores but might be correct


class VerificationResult(BaseModel):
    """Result of verification check"""
    status: VerificationStatus
    is_complete: bool
    confidence: float  # 0-1
    missing_info: Optional[str] = None
    suggested_refinement: Optional[str] = None
    reasoning: str


class VerificationAgent:
    """
    Verification Agent - Validates and refines RAG search results

    Features:
    - LLM-based completeness check
    - Automatic query reformulation
    - Iterative refinement (max iterations)
    - Score-based early stopping

    Usage:
        verifier = VerificationAgent()
        verified_chunks = await verifier.verify_and_refine(
            query="Quelle société gère le nettoyage ?",
            chunks=[...],
            max_iterations=2
        )
    """

    def __init__(self):
        self.llm_service = LLMService()
        self.min_confidence_threshold = 0.40  # Below this, always verify
        self.max_iterations = 2  # Max refinement attempts
        logger.info("verification_agent_initialized",
                   min_confidence=self.min_confidence_threshold,
                   max_iterations=self.max_iterations)

    async def verify_and_refine(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        rag_search_func,  # Function to call for re-search
        max_iterations: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Verify if chunks answer the query, refine if needed

        Args:
            query: Original user query
            chunks: Retrieved chunks from RAG
            rag_search_func: Async function to call for re-search
            max_iterations: Max refinement iterations (default: 2)

        Returns:
            Verified/refined chunks (same format as input)
        """
        if max_iterations is None:
            max_iterations = self.max_iterations

        iteration = 0
        current_chunks = chunks
        refinement_history = []

        while iteration < max_iterations:
            iteration += 1

            # Check if current chunks are sufficient
            verification = await self._check_completeness(query, current_chunks, iteration)

            logger.info("verification_check",
                       iteration=iteration,
                       status=verification.status.value,
                       confidence=f"{verification.confidence:.1%}",
                       is_complete=verification.is_complete)

            # If complete, return
            if verification.is_complete:
                logger.info("verification_passed",
                           iterations=iteration,
                           final_confidence=f"{verification.confidence:.1%}")
                return current_chunks

            # If incomplete and we have a suggested refinement, try again
            if verification.suggested_refinement and iteration < max_iterations:
                logger.info("verification_refining",
                           iteration=iteration,
                           missing_info=verification.missing_info,
                           refined_query=verification.suggested_refinement[:60])

                # Store refinement attempt
                refinement_history.append({
                    "iteration": iteration,
                    "query": verification.suggested_refinement,
                    "reason": verification.missing_info
                })

                # Re-search with refined query
                try:
                    new_chunks = await rag_search_func(
                        query=verification.suggested_refinement,
                        limit=5
                    )

                    if new_chunks:
                        # Merge with existing chunks (deduplicate later)
                        current_chunks = self._merge_chunks(current_chunks, new_chunks)
                        logger.info("verification_refined_chunks_added",
                                   new_chunks=len(new_chunks),
                                   total_chunks=len(current_chunks))
                    else:
                        logger.warning("verification_refinement_returned_no_results")
                        break

                except Exception as e:
                    logger.error("verification_refinement_failed",
                                error=str(e),
                                iteration=iteration)
                    break

            else:
                # No refinement possible or max iterations reached
                logger.warning("verification_cannot_refine",
                              status=verification.status.value,
                              iterations=iteration)
                break

        # Return best chunks we have
        logger.info("verification_completed",
                   total_iterations=iteration,
                   refinements=len(refinement_history),
                   final_chunks=len(current_chunks))

        return current_chunks

    async def _check_completeness(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        iteration: int
    ) -> VerificationResult:
        """
        Check if chunks adequately answer the query

        Args:
            query: User's query
            chunks: Retrieved chunks
            iteration: Current iteration number

        Returns:
            VerificationResult with completeness assessment
        """

        if not chunks:
            return VerificationResult(
                status=VerificationStatus.INCOMPLETE,
                is_complete=False,
                confidence=0.0,
                missing_info="No chunks retrieved",
                suggested_refinement=f"Reformulate: {query}",
                reasoning="No results found"
            )

        # Get top chunk and its score
        top_chunk = chunks[0]
        top_score = top_chunk.get('reranked_score', top_chunk.get('score', 0))

        # Extract text from chunks
        chunks_text = "\n\n---\n\n".join([
            f"[Chunk {i+1}, Score: {c.get('reranked_score', c.get('score', 0)):.1%}]\n{c.get('text', c.get('chunk', ''))[:500]}"
            for i, c in enumerate(chunks[:3])  # Only show top 3 to LLM
        ])

        # Build verification prompt
        prompt = f"""
You are a RAG quality validator. Your job is to check if the retrieved documents answer the user's question AND suggest better search terms if needed.

User Query: "{query}"

Retrieved Documents (with relevance scores):
{chunks_text}

Task: Determine if these documents can answer the query, and ALWAYS suggest a better search query for refinement.

Respond ONLY with valid JSON:
{{
  "can_answer": true/false,
  "confidence": 0.0-1.0,
  "missing_info": "what information is missing or unclear",
  "suggested_search": "alternative search query to find better/additional results",
  "reasoning": "brief explanation"
}}

CRITICAL Rules:
1. **can_answer=true** ONLY if the chunk DIRECTLY contains the specific answer (not just related info)
2. **confidence** should reflect how DIRECTLY the answer is stated (0.9+ = exact answer visible, 0.5 = relevant but vague, 0.3 = tangentially related)
3. **ALWAYS provide suggested_search** - even if can_answer=true, suggest a more specific query that might find better/clearer results
4. **suggested_search** should:
   - Reformulate the query with different keywords
   - Be more specific than the original query
   - Focus on the exact information needed
   - Use synonyms or alternative phrasings
5. If chunk score < 15%, be VERY skeptical - the answer might be wrong or incomplete

Examples:
- Query: "Quelle société gère le nettoyage?" + Chunk mentions "NEC" → can_answer=true, confidence=0.8, suggested_search="nom entreprise contrat nettoyage NEC"
- Query: "Règles balcons?" + Chunk about "interdictions" but unclear → can_answer=true, confidence=0.4, suggested_search="règlement copropriété aménagement balcons autorisations"
"""

        try:
            # Call LLM
            from langchain.schema import HumanMessage, SystemMessage

            messages = [
                SystemMessage(content="You are a RAG verification expert. Respond only in JSON format."),
                HumanMessage(content=prompt)
            ]

            response = await self.llm_service.chat_model.ainvoke(messages)
            llm_output = response.content

            # Parse response
            import json
            import re

            # Clean response
            cleaned = llm_output.strip()
            if '```json' in cleaned:
                cleaned = re.sub(r'```json\s*', '', cleaned)
                cleaned = re.sub(r'```\s*$', '', cleaned)
            elif '```' in cleaned:
                cleaned = re.sub(r'```\s*', '', cleaned, count=1)
                cleaned = re.sub(r'```\s*$', '', cleaned)

            cleaned = cleaned.strip()

            # Extract JSON
            json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if json_match:
                cleaned = json_match.group(0)

            data = json.loads(cleaned)

            # Parse result
            can_answer = data.get('can_answer', False)
            llm_confidence = float(data.get('confidence', 0.5))

            # CRITICAL FIX: Be MUCH more skeptical when chunk scores are low
            # Even if LLM says "can answer", if the chunk score is < 10%, we should refine

            # Combine LLM confidence with chunk scores
            # Weight chunk score more heavily (60% chunk, 40% LLM) because chunk score
            # reflects actual semantic similarity
            combined_confidence = (top_score * 0.6) + (llm_confidence * 0.4)

            # STRICT threshold: If chunk score < 15% (0.15), ALWAYS try to refine
            # Even if LLM thinks it can answer
            if top_score < 0.15:
                is_complete = False
                status = VerificationStatus.LOW_CONFIDENCE
            elif can_answer and combined_confidence >= 0.40:
                # High confidence: accept result
                is_complete = True
                status = VerificationStatus.COMPLETE
            elif can_answer and combined_confidence >= 0.25:
                # Medium confidence: try refinement to find better chunks
                is_complete = False
                status = VerificationStatus.LOW_CONFIDENCE
            elif not can_answer:
                # LLM says cannot answer: definitely refine
                is_complete = False
                status = VerificationStatus.INCOMPLETE
            else:
                is_complete = False
                status = VerificationStatus.WRONG_FOCUS

            return VerificationResult(
                status=status,
                is_complete=is_complete,
                confidence=combined_confidence,
                missing_info=data.get('missing_info'),
                # ALWAYS use suggested_search for refinement, even if can_answer=true
                # This allows us to find better chunks with higher scores
                suggested_refinement=data.get('suggested_search'),
                reasoning=data.get('reasoning', '')
            )

        except Exception as e:
            logger.error("verification_llm_check_failed",
                        error=str(e),
                        iteration=iteration)

            # Fallback: use score-based heuristic
            is_complete = top_score >= self.min_confidence_threshold

            return VerificationResult(
                status=VerificationStatus.COMPLETE if is_complete else VerificationStatus.LOW_CONFIDENCE,
                is_complete=is_complete,
                confidence=top_score,
                missing_info=None if is_complete else "Verification check failed, using score heuristic",
                suggested_refinement=None,
                reasoning=f"Fallback: score-based ({top_score:.1%})"
            )

    def _merge_chunks(
        self,
        existing_chunks: List[Dict[str, Any]],
        new_chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Merge new chunks with existing, avoiding duplicates

        Args:
            existing_chunks: Current chunks
            new_chunks: Newly retrieved chunks

        Returns:
            Merged and deduplicated list
        """
        # Simple deduplication by text content
        seen_texts = set()
        merged = []

        for chunk in existing_chunks + new_chunks:
            text = chunk.get('text', '') or chunk.get('chunk', '') or chunk.get('content', '')
            text_key = text[:200]  # Use first 200 chars as key

            if text_key not in seen_texts:
                seen_texts.add(text_key)
                merged.append(chunk)

        # Sort by score (descending)
        merged.sort(
            key=lambda c: c.get('reranked_score', c.get('score', 0)),
            reverse=True
        )

        return merged

    def should_verify(self, chunks: List[Dict[str, Any]]) -> bool:
        """
        Quick check: Should we verify these results?

        Args:
            chunks: Retrieved chunks

        Returns:
            True if verification recommended
        """
        if not chunks:
            return True  # Always verify empty results

        top_score = chunks[0].get('reranked_score', chunks[0].get('score', 0))

        # Verify if top score is below threshold
        return top_score < self.min_confidence_threshold
