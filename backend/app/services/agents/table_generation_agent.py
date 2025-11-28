"""
Table Generation Agent - Advanced Table Extraction & Generation
Handles structured table extraction from documents and on-demand table generation from prompts
"""

import structlog
import re
import io
import base64
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel
from datetime import datetime
import pandas as pd

from app.services.llm_service import LLMService
from app.core.config import settings

logger = structlog.get_logger()


class TableCell(BaseModel):
    """Single cell in a table"""
    row: int
    col: int
    value: str
    is_header: bool = False


class StructuredTable(BaseModel):
    """Structured table representation"""
    title: Optional[str] = None
    headers: List[str]
    rows: List[List[str]]
    metadata: Dict[str, Any] = {}
    confidence: float = 0.0

    def to_dataframe(self) -> pd.DataFrame:
        """Convert to pandas DataFrame"""
        return pd.DataFrame(self.rows, columns=self.headers)

    def to_csv(self) -> str:
        """Export to CSV"""
        return self.to_dataframe().to_csv(index=False)

    def to_excel_bytes(self) -> bytes:
        """Export to Excel (bytes)"""
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            self.to_dataframe().to_excel(writer, index=False, sheet_name='Data')
        output.seek(0)
        return output.getvalue()

    def to_markdown(self) -> str:
        """Export to Markdown table"""
        md = ""

        if self.title:
            md += f"### {self.title}\n\n"

        # Headers
        md += "| " + " | ".join(self.headers) + " |\n"

        # Separator
        md += "|" + "|".join([" --- " for _ in self.headers]) + "|\n"

        # Rows
        for row in self.rows:
            md += "| " + " | ".join(str(cell) for cell in row) + " |\n"

        return md


class TableGenerationAgent:
    """
    Agent specialized in table extraction and generation

    Capabilities:
    1. Automatic table detection in documents
    2. Structure extraction (columns, rows, merged cells)
    3. Export to JSON/CSV/Excel
    4. On-demand table generation from user prompts
    5. Semantic column understanding

    Technologies:
    - Mistral Vision (Pixtral) for table detection
    - LLM for structure understanding and generation
    - pandas for data manipulation
    - openpyxl for Excel export
    """

    def __init__(self):
        self.llm_service = LLMService()
        logger.info("table_generation_agent_initialized")

    async def extract_tables_from_document(
        self,
        document_text: str,
        image_content: Optional[bytes] = None,
        filename: str = ""
    ) -> List[StructuredTable]:
        """
        Extract all tables from a document

        Args:
            document_text: Full text of document
            image_content: Optional image bytes for vision-based extraction
            filename: Document filename

        Returns:
            List of StructuredTable objects
        """
        try:
            logger.info("extracting_tables_from_document", filename=filename)

            # Strategy 1: Vision-based extraction (if image available)
            if image_content:
                vision_tables = await self._extract_tables_with_vision(image_content)
                if vision_tables:
                    logger.info("vision_extraction_success", table_count=len(vision_tables))
                    return vision_tables

            # Strategy 2: Text-based extraction (fallback)
            text_tables = await self._extract_tables_from_text(document_text)

            logger.info("table_extraction_complete",
                       table_count=len(text_tables),
                       method="text-based")

            return text_tables

        except Exception as e:
            logger.error("table_extraction_failed", error=str(e), exc_info=True)
            return []

    async def _extract_tables_with_vision(
        self,
        image_content: bytes
    ) -> List[StructuredTable]:
        """
        Extract tables using Mistral Vision (Pixtral)

        Args:
            image_content: Image bytes

        Returns:
            List of StructuredTable
        """
        try:
            from langchain_mistralai import ChatMistralAI
            from langchain.schema import HumanMessage

            # Encode image
            image_base64 = base64.b64encode(image_content).decode('utf-8')

            # Vision model
            vision_model = ChatMistralAI(
                model=settings.MISTRAL_VISION_MODEL,
                api_key=settings.MISTRAL_API_KEY,
                temperature=0.0,
            )

            # Prompt for table extraction
            message = HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": """Analyse cette image et extrait TOUS les tableaux présents.

Pour chaque tableau, retourne un JSON array avec cette structure:

[
  {
    "title": "Titre du tableau (si visible)",
    "headers": ["Colonne1", "Colonne2", "Colonne3"],
    "rows": [
      ["valeur1", "valeur2", "valeur3"],
      ["valeur4", "valeur5", "valeur6"]
    ]
  }
]

INSTRUCTIONS:
- Préserve EXACTEMENT les valeurs des cellules (nombres, dates, texte)
- Si une cellule est vide, utilise ""
- Conserve les en-têtes de colonnes tels quels
- Si plusieurs tableaux, retourne-les tous dans l'array
- Retourne UNIQUEMENT le JSON, rien d'autre

JSON:"""
                    },
                    {
                        "type": "image_url",
                        "image_url": f"data:image/jpeg;base64,{image_base64}"
                    }
                ]
            )

            # Invoke vision model
            response = await vision_model.ainvoke([message])

            # Parse JSON response
            import json

            # Extract JSON from response
            json_match = re.search(r'\[.*\]', response.content, re.DOTALL)
            if not json_match:
                logger.warning("no_json_found_in_vision_response")
                return []

            tables_data = json.loads(json_match.group())

            # Convert to StructuredTable objects
            tables = []
            for table_data in tables_data:
                table = StructuredTable(
                    title=table_data.get("title"),
                    headers=table_data.get("headers", []),
                    rows=table_data.get("rows", []),
                    confidence=0.85,  # Vision-based extraction is high confidence
                    metadata={
                        "extraction_method": "mistral_vision",
                        "model": settings.MISTRAL_VISION_MODEL
                    }
                )
                tables.append(table)

            logger.info("vision_table_extraction_success", table_count=len(tables))
            return tables

        except Exception as e:
            logger.error("vision_table_extraction_error", error=str(e), exc_info=True)
            return []

    async def _extract_tables_from_text(
        self,
        document_text: str
    ) -> List[StructuredTable]:
        """
        Extract tables from plain text using LLM

        Args:
            document_text: Full document text

        Returns:
            List of StructuredTable
        """
        try:
            # Use LLM to detect and extract tables
            prompt = f"""Analyse ce document et extrait TOUS les tableaux présents.

Pour chaque tableau, retourne un JSON array:

[
  {{
    "title": "Titre du tableau",
    "headers": ["Colonne1", "Colonne2"],
    "rows": [
      ["valeur1", "valeur2"],
      ["valeur3", "valeur4"]
    ]
  }}
]

DOCUMENT:
{document_text[:4000]}

Si aucun tableau détecté, retourne [].
Retourne UNIQUEMENT le JSON.

JSON:"""

            response = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.0,
                max_tokens=2000
            )

            # Parse JSON
            import json
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if not json_match:
                return []

            tables_data = json.loads(json_match.group())

            tables = []
            for table_data in tables_data:
                table = StructuredTable(
                    title=table_data.get("title"),
                    headers=table_data.get("headers", []),
                    rows=table_data.get("rows", []),
                    confidence=0.75,  # Text-based is medium-high confidence
                    metadata={
                        "extraction_method": "llm_text",
                        "model": "mistral-large"
                    }
                )
                tables.append(table)

            return tables

        except Exception as e:
            logger.error("text_table_extraction_error", error=str(e), exc_info=True)
            return []

    async def generate_table_from_prompt(
        self,
        user_prompt: str,
        document_text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> StructuredTable:
        """
        Generate a table based on user prompt and document content

        This is the KILLER FEATURE: User says "fais-moi un tableau avec fournisseur, montant, date"
        and we generate it automatically!

        Args:
            user_prompt: User's request (e.g., "tableau avec fournisseur, montant TTC, date")
            document_text: Source document text
            context: Optional context (document metadata, etc.)

        Returns:
            StructuredTable matching user's request
        """
        try:
            logger.info("generating_table_from_prompt",
                       prompt=user_prompt[:100],
                       text_length=len(document_text))

            # Extract column requirements from prompt
            columns = await self._extract_column_requirements(user_prompt)

            logger.info("columns_extracted", columns=columns)

            # Generate table with LLM
            prompt = f"""Génère un tableau à partir de ce document.

L'utilisateur demande: "{user_prompt}"

Colonnes requises: {', '.join(columns)}

DOCUMENT:
{document_text[:3000]}

Retourne un JSON avec cette structure exacte:

{{
  "title": "Titre descriptif du tableau",
  "headers": {columns},
  "rows": [
    ["valeur_colonne1", "valeur_colonne2", ...],
    ["valeur_colonne1", "valeur_colonne2", ...],
    ...
  ]
}}

RÈGLES CRITIQUES:
- Extrais TOUTES les lignes pertinentes du document
- Préserve les valeurs exactes (montants avec €, dates format DD/MM/YYYY)
- Si une valeur est absente, utilise "N/A"
- Ordonne les lignes chronologiquement si des dates sont présentes
- Headers = EXACTEMENT les colonnes demandées

Retourne UNIQUEMENT le JSON.

JSON:"""

            response = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.0,
                max_tokens=2000
            )

            # Parse JSON
            import json
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                raise ValueError("No valid JSON found in LLM response")

            table_data = json.loads(json_match.group())

            table = StructuredTable(
                title=table_data.get("title", "Tableau généré"),
                headers=table_data.get("headers", columns),
                rows=table_data.get("rows", []),
                confidence=0.80,
                metadata={
                    "generation_method": "llm_prompted",
                    "user_prompt": user_prompt,
                    "generated_at": datetime.now().isoformat()
                }
            )

            logger.info("table_generation_success",
                       headers=table.headers,
                       row_count=len(table.rows))

            return table

        except Exception as e:
            logger.error("table_generation_failed", error=str(e), exc_info=True)

            # Return empty table with requested columns
            return StructuredTable(
                title="Erreur de génération",
                headers=await self._extract_column_requirements(user_prompt),
                rows=[],
                confidence=0.0,
                metadata={"error": str(e)}
            )

    async def _extract_column_requirements(
        self,
        user_prompt: str
    ) -> List[str]:
        """
        Extract column names from user prompt

        Examples:
        - "tableau avec fournisseur, montant TTC, date" → ["Fournisseur", "Montant TTC", "Date"]
        - "fais un tableau: nom, adresse, téléphone" → ["Nom", "Adresse", "Téléphone"]

        Args:
            user_prompt: User's request

        Returns:
            List of column names
        """
        try:
            # Use LLM to extract column requirements
            prompt = f"""Extrait les noms de colonnes demandés par l'utilisateur.

Demande utilisateur: "{user_prompt}"

Retourne un JSON array simple avec les noms de colonnes:

["Colonne1", "Colonne2", "Colonne3"]

RÈGLES:
- Capitalise la première lettre de chaque colonne
- Utilise les termes exacts de l'utilisateur
- Si aucune colonne spécifiée, devine les colonnes pertinentes pour le contexte

Retourne UNIQUEMENT le JSON array.

JSON:"""

            response = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.0,
                max_tokens=200
            )

            # Parse JSON
            import json
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                columns = json.loads(json_match.group())
                return columns

            # Fallback: basic regex extraction
            return self._extract_columns_regex(user_prompt)

        except Exception as e:
            logger.error("column_extraction_failed", error=str(e))
            return self._extract_columns_regex(user_prompt)

    def _extract_columns_regex(self, user_prompt: str) -> List[str]:
        """Fallback regex-based column extraction"""
        # Look for comma-separated items after keywords
        patterns = [
            r'tableau.*?avec[:\s]+(.+)',
            r'colonnes[:\s]+(.+)',
            r'affiche[:\s]+(.+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, user_prompt, re.IGNORECASE)
            if match:
                items = match.group(1).split(',')
                # Clean and capitalize
                columns = [item.strip().capitalize() for item in items]
                return columns

        # Default fallback
        return ["Colonne 1", "Colonne 2", "Colonne 3"]

    async def compare_tables(
        self,
        table1: StructuredTable,
        table2: StructuredTable
    ) -> Dict[str, Any]:
        """
        Compare two tables and identify differences

        Use Case: "Compare ces deux devis"

        Args:
            table1: First table
            table2: Second table

        Returns:
            Comparison result with differences, additions, deletions
        """
        try:
            df1 = table1.to_dataframe()
            df2 = table2.to_dataframe()

            # Basic comparison
            differences = {
                "shape_diff": {
                    "table1_rows": len(df1),
                    "table2_rows": len(df2),
                    "table1_cols": len(df1.columns),
                    "table2_cols": len(df2.columns)
                },
                "column_diff": {
                    "common": list(set(df1.columns) & set(df2.columns)),
                    "only_table1": list(set(df1.columns) - set(df2.columns)),
                    "only_table2": list(set(df2.columns) - set(df1.columns))
                },
                "summary": ""
            }

            # Generate natural language summary with LLM
            prompt = f"""Compare ces deux tableaux et résume les différences principales.

TABLEAU 1:
{table1.to_markdown()}

TABLEAU 2:
{table2.to_markdown()}

Résume en 2-3 phrases les différences clés (nombre de lignes, colonnes différentes, valeurs divergentes).

Résumé:"""

            summary = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.3,
                max_tokens=300
            )

            differences["summary"] = summary.strip()

            return differences

        except Exception as e:
            logger.error("table_comparison_failed", error=str(e), exc_info=True)
            return {"error": str(e)}
