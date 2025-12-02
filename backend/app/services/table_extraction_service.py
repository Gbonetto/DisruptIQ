"""
Table Extraction Service - Détection et parsing de tableaux dans les documents
Phase RAG World-Class - DisruptIQ SMA

Ce module détecte les tableaux dans le texte OCR et les parse en structures
exploitables pour:
- Indexation séparée par ligne (meilleure recherche)
- Génération de résumés de tableaux
- Réponses formatées en tableau

Patterns détectés:
- Tableaux avec séparateurs | ou :
- Listes à puces avec montants alignés
- Tableaux ASCII avec tirets/plus

Author: Claude Code - RAG World-Class
Date: December 2024
"""

import re
import structlog
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = structlog.get_logger()


class TableType(Enum):
    """Types de tableaux détectés"""
    PIPE_SEPARATED = "pipe"       # | col1 | col2 |
    COLON_SEPARATED = "colon"     # Libellé : Valeur
    ALIGNED_AMOUNTS = "amounts"   # Texte........ 123,45€
    ASCII_TABLE = "ascii"         # +---+---+
    BULLET_LIST = "bullet"        # - Item: valeur


@dataclass
class TableCell:
    """Cellule de tableau"""
    value: str
    row_index: int
    col_index: int
    is_header: bool = False
    is_amount: bool = False
    normalized_value: Optional[str] = None  # Ex: "12500" pour "12 500,00 €"


@dataclass
class TableRow:
    """Ligne de tableau"""
    cells: List[TableCell]
    is_header: bool = False
    raw_text: str = ""


@dataclass
class ExtractedTable:
    """Tableau extrait avec métadonnées"""
    table_type: TableType
    headers: List[str]
    rows: List[TableRow]
    raw_text: str
    start_pos: int
    end_pos: int
    confidence: float
    summary: Optional[str] = None

    @property
    def column_count(self) -> int:
        return len(self.headers) if self.headers else 0

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def to_markdown(self) -> str:
        """Convertit le tableau en markdown"""
        if not self.headers:
            return self.raw_text

        lines = []
        # Headers
        lines.append("| " + " | ".join(self.headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(self.headers)) + " |")

        # Rows
        for row in self.rows:
            cells = [c.value for c in row.cells]
            # Pad if needed
            while len(cells) < len(self.headers):
                cells.append("")
            lines.append("| " + " | ".join(cells[:len(self.headers)]) + " |")

        return "\n".join(lines)

    def to_row_chunks(self) -> List[Dict[str, Any]]:
        """Génère un chunk par ligne pour indexation séparée"""
        chunks = []

        for i, row in enumerate(self.rows):
            # Skip header rows
            if row.is_header:
                continue

            # Create key-value pairs
            pairs = []
            for j, cell in enumerate(row.cells):
                if j < len(self.headers):
                    pairs.append(f"{self.headers[j]}: {cell.value}")

            chunk_text = " | ".join(pairs)

            chunks.append({
                "text": chunk_text,
                "row_index": i,
                "metadata": {
                    "is_table_row": True,
                    "table_type": self.table_type.value,
                    "row_data": {
                        self.headers[j]: cell.value
                        for j, cell in enumerate(row.cells)
                        if j < len(self.headers)
                    }
                }
            })

        return chunks


class TableExtractionService:
    """
    Service de détection et extraction de tableaux.

    Utilise des patterns regex et heuristiques pour détecter
    différents formats de tableaux dans le texte OCR.
    """

    # Patterns de détection
    PIPE_TABLE_PATTERN = re.compile(
        r'^\s*\|[^|]+\|[^|]+\|',
        re.MULTILINE
    )

    COLON_TABLE_PATTERN = re.compile(
        r'^([A-ZÀ-Ü][^:]{2,50})\s*:\s*(.+)$',
        re.MULTILINE | re.IGNORECASE
    )

    AMOUNT_PATTERN = re.compile(
        r'(\d[\d\s,\.]*(?:€|EUR|euros?))',
        re.IGNORECASE
    )

    ASCII_TABLE_PATTERN = re.compile(
        r'^\s*\+[-+]+\+\s*$',
        re.MULTILINE
    )

    ALIGNED_AMOUNT_PATTERN = re.compile(
        r'^(.{10,50})\s{2,}(\d[\d\s,\.]*(?:€|EUR|euros?|\d{1,3}(?:\s?\d{3})*(?:,\d{2})?))$',
        re.MULTILINE | re.IGNORECASE
    )

    def __init__(self):
        self._amount_normalizer = re.compile(r'[^\d,\.]')

    def detect_tables(self, text: str) -> List[ExtractedTable]:
        """
        Détecte tous les tableaux dans le texte.

        Args:
            text: Texte source (OCR ou PDF)

        Returns:
            Liste des tableaux détectés
        """
        tables = []

        # 1. Detect pipe-separated tables
        tables.extend(self._detect_pipe_tables(text))

        # 2. Detect colon-separated key-value lists
        tables.extend(self._detect_colon_tables(text))

        # 3. Detect aligned amounts (factures, devis)
        tables.extend(self._detect_aligned_amount_tables(text))

        # 4. Detect ASCII tables
        tables.extend(self._detect_ascii_tables(text))

        # Remove overlapping tables (keep highest confidence)
        tables = self._remove_overlaps(tables)

        logger.info("tables_detected",
                   count=len(tables),
                   types=[t.table_type.value for t in tables])

        return tables

    def _detect_pipe_tables(self, text: str) -> List[ExtractedTable]:
        """Détecte les tableaux avec séparateurs |"""
        tables = []
        lines = text.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            # Check if line starts a pipe table
            if '|' in line and line.count('|') >= 2:
                table_lines = [line]
                start_pos = text.find(line)
                j = i + 1

                # Collect consecutive pipe lines
                while j < len(lines):
                    next_line = lines[j].strip()
                    if '|' in next_line and next_line.count('|') >= 2:
                        table_lines.append(next_line)
                        j += 1
                    elif next_line == '' or re.match(r'^[-|+]+$', next_line):
                        j += 1  # Skip separator or empty line
                    else:
                        break

                # Need at least 2 data rows (+ optional header)
                if len(table_lines) >= 2:
                    table = self._parse_pipe_table(table_lines, start_pos)
                    if table:
                        tables.append(table)

                i = j
            else:
                i += 1

        return tables

    def _parse_pipe_table(self, lines: List[str], start_pos: int) -> Optional[ExtractedTable]:
        """Parse un tableau pipe-separated"""
        try:
            # Split each line by |
            rows = []
            for line in lines:
                # Remove leading/trailing pipes and split
                cells = [c.strip() for c in line.strip('|').split('|')]
                cells = [c for c in cells if c]  # Remove empty
                if cells:
                    rows.append(cells)

            if len(rows) < 2:
                return None

            # First row is header
            headers = rows[0]

            # Skip separator rows (all dashes)
            data_rows = []
            for row in rows[1:]:
                if not all(re.match(r'^[-:]+$', cell) for cell in row):
                    data_rows.append(row)

            # Build TableRow objects
            table_rows = []
            for i, row in enumerate(data_rows):
                cells = [
                    TableCell(
                        value=cell,
                        row_index=i,
                        col_index=j,
                        is_amount=bool(self.AMOUNT_PATTERN.search(cell))
                    )
                    for j, cell in enumerate(row)
                ]
                table_rows.append(TableRow(
                    cells=cells,
                    raw_text=" | ".join(row)
                ))

            return ExtractedTable(
                table_type=TableType.PIPE_SEPARATED,
                headers=headers,
                rows=table_rows,
                raw_text="\n".join(lines),
                start_pos=start_pos,
                end_pos=start_pos + len("\n".join(lines)),
                confidence=0.9
            )

        except Exception as e:
            logger.warning("pipe_table_parse_failed", error=str(e))
            return None

    def _detect_colon_tables(self, text: str) -> List[ExtractedTable]:
        """Détecte les listes clé: valeur"""
        tables = []
        lines = text.split('\n')

        current_pairs = []
        start_idx = None

        for i, line in enumerate(lines):
            match = self.COLON_TABLE_PATTERN.match(line.strip())
            if match:
                if start_idx is None:
                    start_idx = text.find(line)
                current_pairs.append((match.group(1).strip(), match.group(2).strip()))
            else:
                # End of current sequence
                if len(current_pairs) >= 3:  # At least 3 key-value pairs
                    table = self._build_colon_table(current_pairs, start_idx)
                    if table:
                        tables.append(table)
                current_pairs = []
                start_idx = None

        # Handle last sequence
        if len(current_pairs) >= 3:
            table = self._build_colon_table(current_pairs, start_idx or 0)
            if table:
                tables.append(table)

        return tables

    def _build_colon_table(
        self,
        pairs: List[Tuple[str, str]],
        start_pos: int
    ) -> Optional[ExtractedTable]:
        """Construit un tableau depuis des paires clé:valeur"""
        try:
            headers = ["Libellé", "Valeur"]
            rows = []

            for i, (key, value) in enumerate(pairs):
                cells = [
                    TableCell(value=key, row_index=i, col_index=0),
                    TableCell(
                        value=value,
                        row_index=i,
                        col_index=1,
                        is_amount=bool(self.AMOUNT_PATTERN.search(value))
                    )
                ]
                rows.append(TableRow(
                    cells=cells,
                    raw_text=f"{key}: {value}"
                ))

            raw_text = "\n".join([f"{k}: {v}" for k, v in pairs])

            return ExtractedTable(
                table_type=TableType.COLON_SEPARATED,
                headers=headers,
                rows=rows,
                raw_text=raw_text,
                start_pos=start_pos,
                end_pos=start_pos + len(raw_text),
                confidence=0.8
            )

        except Exception as e:
            logger.warning("colon_table_build_failed", error=str(e))
            return None

    def _detect_aligned_amount_tables(self, text: str) -> List[ExtractedTable]:
        """Détecte les tableaux avec montants alignés (factures)"""
        tables = []
        matches = list(self.ALIGNED_AMOUNT_PATTERN.finditer(text))

        if len(matches) < 2:
            return tables

        # Group consecutive matches
        current_group = []
        last_end = 0

        for match in matches:
            # Check if this match is close to the previous one
            if match.start() - last_end < 200:  # Within 200 chars
                current_group.append(match)
            else:
                # Build table from previous group
                if len(current_group) >= 2:
                    table = self._build_amount_table(current_group, text)
                    if table:
                        tables.append(table)
                current_group = [match]

            last_end = match.end()

        # Handle last group
        if len(current_group) >= 2:
            table = self._build_amount_table(current_group, text)
            if table:
                tables.append(table)

        return tables

    def _build_amount_table(
        self,
        matches: List[re.Match],
        text: str
    ) -> Optional[ExtractedTable]:
        """Construit un tableau depuis des lignes avec montants alignés"""
        try:
            headers = ["Description", "Montant"]
            rows = []

            for i, match in enumerate(matches):
                description = match.group(1).strip()
                amount = match.group(2).strip()

                cells = [
                    TableCell(value=description, row_index=i, col_index=0),
                    TableCell(
                        value=amount,
                        row_index=i,
                        col_index=1,
                        is_amount=True,
                        normalized_value=self._normalize_amount(amount)
                    )
                ]
                rows.append(TableRow(
                    cells=cells,
                    raw_text=f"{description}: {amount}"
                ))

            start_pos = matches[0].start()
            end_pos = matches[-1].end()
            raw_text = text[start_pos:end_pos]

            return ExtractedTable(
                table_type=TableType.ALIGNED_AMOUNTS,
                headers=headers,
                rows=rows,
                raw_text=raw_text,
                start_pos=start_pos,
                end_pos=end_pos,
                confidence=0.85
            )

        except Exception as e:
            logger.warning("amount_table_build_failed", error=str(e))
            return None

    def _detect_ascii_tables(self, text: str) -> List[ExtractedTable]:
        """Détecte les tableaux ASCII (+---+---+)"""
        # Not implemented yet - lower priority
        return []

    def _normalize_amount(self, amount: str) -> str:
        """Normalise un montant pour recherche exacte"""
        # Remove all non-digits except comma/dot
        cleaned = self._amount_normalizer.sub('', amount)
        # Replace comma with dot for decimal
        cleaned = cleaned.replace(',', '.')
        # Remove trailing dots
        cleaned = cleaned.rstrip('.')
        return cleaned

    def _remove_overlaps(self, tables: List[ExtractedTable]) -> List[ExtractedTable]:
        """Supprime les tableaux qui se chevauchent (garde le plus confiant)"""
        if len(tables) <= 1:
            return tables

        # Sort by start position
        tables.sort(key=lambda t: t.start_pos)

        result = []
        for table in tables:
            # Check overlap with last added
            if result:
                last = result[-1]
                if table.start_pos < last.end_pos:
                    # Overlap - keep higher confidence
                    if table.confidence > last.confidence:
                        result[-1] = table
                    continue

            result.append(table)

        return result

    def extract_table_context(
        self,
        table: ExtractedTable,
        full_text: str,
        context_chars: int = 200
    ) -> str:
        """Extrait le contexte autour d'un tableau"""
        start = max(0, table.start_pos - context_chars)
        end = min(len(full_text), table.end_pos + context_chars)

        context_before = full_text[start:table.start_pos].strip()
        context_after = full_text[table.end_pos:end].strip()

        return f"{context_before}\n\n[TABLEAU]\n{table.to_markdown()}\n[/TABLEAU]\n\n{context_after}"

    def generate_table_summary(self, table: ExtractedTable) -> str:
        """Génère un résumé textuel du tableau"""
        lines = []

        lines.append(f"Tableau avec {table.row_count} lignes et {table.column_count} colonnes.")

        if table.headers:
            lines.append(f"Colonnes: {', '.join(table.headers)}")

        # Find amounts
        amounts = []
        for row in table.rows:
            for cell in row.cells:
                if cell.is_amount:
                    amounts.append(cell.value)

        if amounts:
            lines.append(f"Montants trouvés: {', '.join(amounts[:5])}")
            if len(amounts) > 5:
                lines.append(f"... et {len(amounts) - 5} autres montants")

        return " ".join(lines)


# Singleton
_table_extraction_service: Optional[TableExtractionService] = None


def get_table_extraction_service() -> TableExtractionService:
    """Retourne l'instance singleton du Table Extraction Service"""
    global _table_extraction_service
    if _table_extraction_service is None:
        _table_extraction_service = TableExtractionService()
    return _table_extraction_service
