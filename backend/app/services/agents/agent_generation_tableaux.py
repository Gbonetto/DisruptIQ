"""
Agent de Génération de Tableaux - Extraction et Génération Avancée de Tableaux
Gère l'extraction structurée de tableaux depuis des documents et la génération de tableaux à la demande depuis des prompts
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


class CelluleTableau(BaseModel):
    """Cellule unique dans un tableau"""
    ligne: int
    colonne: int
    valeur: str
    est_entete: bool = False


class TableauStructure(BaseModel):
    """Représentation structurée d'un tableau"""
    titre: Optional[str] = None
    entetes: List[str]
    lignes: List[List[str]]
    metadonnees: Dict[str, Any] = {}
    confiance: float = 0.0

    def vers_dataframe(self) -> pd.DataFrame:
        """Convertir en pandas DataFrame"""
        return pd.DataFrame(self.lignes, columns=self.entetes)

    def vers_csv(self) -> str:
        """Exporter en CSV"""
        return self.vers_dataframe().to_csv(index=False)

    def vers_bytes_excel(self) -> bytes:
        """Exporter en Excel (bytes)"""
        sortie = io.BytesIO()
        with pd.ExcelWriter(sortie, engine='openpyxl') as writer:
            self.vers_dataframe().to_excel(writer, index=False, sheet_name='Data')
        sortie.seek(0)
        return sortie.getvalue()

    def vers_markdown(self) -> str:
        """Exporter en tableau Markdown"""
        md = ""

        if self.titre:
            md += f"### {self.titre}\n\n"

        # En-têtes
        md += "| " + " | ".join(self.entetes) + " |\n"

        # Séparateur
        md += "|" + "|".join([" --- " for _ in self.entetes]) + "|\n"

        # Lignes
        for ligne in self.lignes:
            md += "| " + " | ".join(str(cellule) for cellule in ligne) + " |\n"

        return md


class AgentGenerationTableaux:
    """
    Agent spécialisé dans l'extraction et la génération de tableaux

    Capacités:
    1. Détection automatique de tableaux dans les documents
    2. Extraction de structure (colonnes, lignes, cellules fusionnées)
    3. Export en JSON/CSV/Excel
    4. Génération de tableaux à la demande depuis des prompts utilisateur
    5. Compréhension sémantique des colonnes

    Technologies:
    - Mistral Vision (Pixtral) pour la détection de tableaux
    - LLM pour la compréhension de structure et la génération
    - pandas pour la manipulation de données
    - openpyxl pour l'export Excel
    """

    def __init__(self):
        self.service_llm = LLMService()
        logger.info("agent_generation_tableaux_initialise")

    async def extraire_tableaux_depuis_document(
        self,
        texte_document: str,
        contenu_image: Optional[bytes] = None,
        nom_fichier: str = ""
    ) -> List[TableauStructure]:
        """
        Extraire tous les tableaux d'un document

        Args:
            texte_document: Texte complet du document
            contenu_image: Bytes d'image optionnels pour l'extraction basée sur la vision
            nom_fichier: Nom de fichier du document

        Returns:
            Liste d'objets TableauStructure
        """
        try:
            logger.info("extraction_tableaux_depuis_document", nom_fichier=nom_fichier)

            # Stratégie 1: Extraction basée sur la vision (si image disponible)
            if contenu_image:
                tableaux_vision = await self._extraire_tableaux_avec_vision(contenu_image)
                if tableaux_vision:
                    logger.info("extraction_vision_reussie", nombre_tableaux=len(tableaux_vision))
                    return tableaux_vision

            # Stratégie 2: Extraction basée sur le texte (repli)
            tableaux_texte = await self._extraire_tableaux_depuis_texte(texte_document)

            logger.info("extraction_tableaux_terminee",
                       nombre_tableaux=len(tableaux_texte),
                       methode="basee-texte")

            return tableaux_texte

        except Exception as e:
            logger.error("echec_extraction_tableaux", error=str(e), exc_info=True)
            return []

    async def _extraire_tableaux_avec_vision(
        self,
        contenu_image: bytes
    ) -> List[TableauStructure]:
        """
        Extraire des tableaux en utilisant Mistral Vision (Pixtral)

        Args:
            contenu_image: Bytes d'image

        Returns:
            Liste de TableauStructure
        """
        try:
            from langchain_mistralai import ChatMistralAI
            from langchain.schema import HumanMessage

            # Encoder l'image
            image_base64 = base64.b64encode(contenu_image).decode('utf-8')

            # Modèle de vision
            modele_vision = ChatMistralAI(
                model=settings.MISTRAL_VISION_MODEL,
                api_key=settings.MISTRAL_API_KEY,
                temperature=0.0,
            )

            # Prompt pour l'extraction de tableaux
            message = HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": """Analyse cette image et extrait TOUS les tableaux présents.

Pour chaque tableau, retourne un JSON array avec cette structure:

[
  {
    "titre": "Titre du tableau (si visible)",
    "entetes": ["Colonne1", "Colonne2", "Colonne3"],
    "lignes": [
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

            # Invoquer le modèle de vision
            reponse = await modele_vision.ainvoke([message])

            # Parser la réponse JSON
            import json

            # Extraire le JSON de la réponse
            correspondance_json = re.search(r'\[.*\]', reponse.content, re.DOTALL)
            if not correspondance_json:
                logger.warning("aucun_json_trouve_dans_reponse_vision")
                return []

            donnees_tableaux = json.loads(correspondance_json.group())

            # Convertir en objets TableauStructure
            tableaux = []
            for donnees_tableau in donnees_tableaux:
                tableau = TableauStructure(
                    titre=donnees_tableau.get("titre"),
                    entetes=donnees_tableau.get("entetes", []),
                    lignes=donnees_tableau.get("lignes", []),
                    confiance=0.85,
                    metadonnees={
                        "methode_extraction": "mistral_vision",
                        "modele": settings.MISTRAL_VISION_MODEL
                    }
                )
                tableaux.append(tableau)

            logger.info("extraction_tableau_vision_reussie", nombre_tableaux=len(tableaux))
            return tableaux

        except Exception as e:
            logger.error("erreur_extraction_tableau_vision", error=str(e), exc_info=True)
            return []

    async def _extraire_tableaux_depuis_texte(
        self,
        texte_document: str
    ) -> List[TableauStructure]:
        """
        Extraire des tableaux depuis du texte brut en utilisant le LLM

        Args:
            texte_document: Texte complet du document

        Returns:
            Liste de TableauStructure
        """
        try:
            prompt = f"""Analyse ce document et extrait TOUS les tableaux présents.

Pour chaque tableau, retourne un JSON array:

[
  {{
    "titre": "Titre du tableau",
    "entetes": ["Colonne1", "Colonne2"],
    "lignes": [
      ["valeur1", "valeur2"],
      ["valeur3", "valeur4"]
    ]
  }}
]

DOCUMENT:
{texte_document[:4000]}

Si aucun tableau détecté, retourne [].
Retourne UNIQUEMENT le JSON.

JSON:"""

            reponse = await self.service_llm.generate_response(
                prompt=prompt,
                temperature=0.0,
                max_tokens=2000
            )

            import json
            correspondance_json = re.search(r'\[.*\]', reponse, re.DOTALL)
            if not correspondance_json:
                return []

            donnees_tableaux = json.loads(correspondance_json.group())

            tableaux = []
            for donnees_tableau in donnees_tableaux:
                tableau = TableauStructure(
                    titre=donnees_tableau.get("titre"),
                    entetes=donnees_tableau.get("entetes", []),
                    lignes=donnees_tableau.get("lignes", []),
                    confiance=0.75,
                    metadonnees={
                        "methode_extraction": "llm_texte",
                        "modele": "mistral-large"
                    }
                )
                tableaux.append(tableau)

            return tableaux

        except Exception as e:
            logger.error("erreur_extraction_tableau_texte", error=str(e), exc_info=True)
            return []

    async def generer_tableau_depuis_prompt(
        self,
        prompt_utilisateur: str,
        texte_document: str,
        contexte: Optional[Dict[str, Any]] = None
    ) -> TableauStructure:
        """
        Générer un tableau basé sur le prompt utilisateur et le contenu du document

        Args:
            prompt_utilisateur: Demande de l'utilisateur
            texte_document: Texte du document source
            contexte: Contexte optionnel

        Returns:
            TableauStructure correspondant à la demande
        """
        try:
            logger.info("generation_tableau_depuis_prompt",
                       prompt=prompt_utilisateur[:100])

            colonnes = await self._extraire_exigences_colonnes(prompt_utilisateur)

            prompt = f"""Génère un tableau à partir de ce document.

L'utilisateur demande: "{prompt_utilisateur}"

Colonnes requises: {', '.join(colonnes)}

DOCUMENT:
{texte_document[:3000]}

Retourne un JSON:

{{
  "titre": "Titre",
  "entetes": {colonnes},
  "lignes": [...]
}}

Retourne UNIQUEMENT le JSON.

JSON:"""

            reponse = await self.service_llm.generate_response(
                prompt=prompt,
                temperature=0.0,
                max_tokens=2000
            )

            import json
            correspondance_json = re.search(r'\{.*\}', reponse, re.DOTALL)
            if not correspondance_json:
                raise ValueError("Aucun JSON trouvé")

            donnees_tableau = json.loads(correspondance_json.group())

            tableau = TableauStructure(
                titre=donnees_tableau.get("titre", "Tableau généré"),
                entetes=donnees_tableau.get("entetes", colonnes),
                lignes=donnees_tableau.get("lignes", []),
                confiance=0.80,
                metadonnees={
                    "methode_generation": "llm_prompte",
                    "prompt_utilisateur": prompt_utilisateur
                }
            )

            logger.info("generation_tableau_reussie",
                       nombre_lignes=len(tableau.lignes))

            return tableau

        except Exception as e:
            logger.error("echec_generation_tableau", error=str(e))
            return TableauStructure(
                titre="Erreur",
                entetes=await self._extraire_exigences_colonnes(prompt_utilisateur),
                lignes=[],
                confiance=0.0
            )

    async def _extraire_exigences_colonnes(self, prompt_utilisateur: str) -> List[str]:
        """Extraire les noms de colonnes depuis le prompt"""
        try:
            prompt = f"""Extrait les colonnes demandées.

Demande: "{prompt_utilisateur}"

Retourne un JSON array:

["Colonne1", "Colonne2"]

JSON:"""

            reponse = await self.service_llm.generate_response(
                prompt=prompt,
                temperature=0.0,
                max_tokens=200
            )

            import json
            correspondance_json = re.search(r'\[.*\]', reponse, re.DOTALL)
            if correspondance_json:
                return json.loads(correspondance_json.group())

            return self._extraire_colonnes_regex(prompt_utilisateur)

        except Exception as e:
            return self._extraire_colonnes_regex(prompt_utilisateur)

    def _extraire_colonnes_regex(self, prompt_utilisateur: str) -> List[str]:
        """Extraction regex en repli"""
        motifs = [
            r'tableau.*?avec[:\s]+(.+)',
            r'colonnes[:\s]+(.+)',
        ]

        for motif in motifs:
            correspondance = re.search(motif, prompt_utilisateur, re.IGNORECASE)
            if correspondance:
                elements = correspondance.group(1).split(',')
                return [element.strip().capitalize() for element in elements]

        return ["Colonne 1", "Colonne 2"]
