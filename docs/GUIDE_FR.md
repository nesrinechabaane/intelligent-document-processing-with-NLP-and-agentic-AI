# Guide complet (français) — installer, lancer, tester, publier sur GitHub

## 1. Ce que fait le projet (en 30 secondes)

Tu donnes un document technique (fiche technique, rapport de maintenance, rapport d'inspection ;
texte, PDF ou image scannée). Le système :

1. **lit** le document (extraction du texte, OCR si nécessaire) ;
2. **extrait** les informations importantes : identifiant, date, équipement, normes (ISO/IEC/EN),
   mesures (pression, température, tension…), anomalies décrites ;
3. **vérifie** : une mesure dépasse-t-elle la limite ? champs manquants ? valeur impossible ? date incohérente ?
4. **décide et agit** via un agent : ticket, alerte, relecture humaine, archivage ;
5. **génère un rapport** Markdown + JSON.

Par défaut tout fonctionne **hors-ligne, sans clé API**. Un LLM (Claude) peut en option choisir les actions.

## 2. Prérequis

| Outil | Pourquoi | Installation |
|---|---|---|
| Python 3.10 ou plus | exécuter le projet | https://www.python.org/downloads/ (cocher « Add to PATH » sous Windows) |
| Git | versionner et publier | https://git-scm.com/downloads |
| Tesseract OCR | lire les images scannées (optionnel pour .txt/.pdf) | Windows : installeur https://github.com/UB-Mannheim/tesseract/wiki (cocher le français) puis ajouter le dossier au PATH · macOS : `brew install tesseract tesseract-lang` · Linux : `sudo apt install tesseract-ocr tesseract-ocr-fra` |

Vérifier : `python --version`, `git --version`, `tesseract --version`.

## 3. Installation

```bash
cd idp-agent
python -m venv .venv

# Activer l'environnement
source .venv/bin/activate          # macOS / Linux
.venv\Scripts\Activate.ps1         # Windows PowerShell
.venv\Scripts\activate.bat         # Windows cmd

pip install -e ".[dev]"            # le projet + pytest, ruff, mypy
```

> PowerShell refuse d'activer l'environnement ? Lancer une fois :
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

Extras facultatifs : `pip install -e ".[api]"` (serveur REST), `".[nlp]"` (spaCy), `".[llm]"` (Claude),
ou tout d'un coup `".[all]"`.

## 4. Premier lancement (démo en 3 commandes)

```bash
idp generate-samples                # crée data/samples et data/samples_hard (documents fictifs + vérité terrain)
idp process data/samples -o output  # traite tous les documents
idp evaluate data/samples           # mesure la qualité (précision / rappel / F1)
```

Ouvre ensuite `output/reports/` (rapports `.md`) et `output/actions/` (tickets, alertes, file de relecture).
Si la commande `idp` n'est pas trouvée, utilise `python -m idp_agent ...` à la place.

Traiter **tes propres documents** : `idp process mon_document.pdf mon_dossier/ -o resultats`.

## 5. API REST

```bash
pip install -e ".[api]"
idp serve
```

Ouvre http://127.0.0.1:8000/docs : tu peux téléverser un fichier depuis le navigateur (route `POST /process`).

## 6. Mode LLM (optionnel)

```bash
pip install -e ".[llm]"
# macOS / Linux
export ANTHROPIC_API_KEY="ta_clé"
# Windows PowerShell
$env:ANTHROPIC_API_KEY="ta_clé"

idp process data/samples --llm anthropic
```

Sans clé ou en cas d'erreur du modèle, le projet retombe automatiquement sur les règles : il ne plante pas.
**Ne mets jamais ta clé dans le code ni dans Git** (le fichier `.env` est ignoré par `.gitignore`).

## 7. Tests et qualité

```bash
pytest                       # 94 tests
pytest --cov                 # avec couverture
ruff check . && ruff format --check .
mypy src
```

## 8. Publier sur GitHub (pas à pas)

### 8.1 Personnaliser avant de publier
- `LICENSE` et `pyproject.toml` : remplacer `Your Name` par ton nom.
- `README.md` : remplacer `YOUR_USERNAME` par ton identifiant GitHub (3 occurrences : badge CI, `git clone`).
- Ajouter une capture d'écran de `/docs` (API) dans le README si tu veux un rendu plus visuel.

### 8.2 Créer le dépôt
Sur https://github.com/new : nom `idp-agent` (ou `intelligent-document-processing`), **public**,
et **ne coche pas** « Add a README » (il existe déjà).

### 8.3 Premier commit et envoi

```bash
cd idp-agent
git init -b main
git add .
git status                      # vérifier : pas de .venv, pas de output/, pas de .env
git commit -m "Initial commit: intelligent document processing with NLP and agentic AI"
git remote add origin https://github.com/TON_IDENTIFIANT/idp-agent.git
git push -u origin main
```

À la première connexion, GitHub demande un **Personal Access Token** (Settings → Developer settings →
Tokens) ou une connexion via le navigateur / GitHub CLI (`gh auth login`).

### 8.4 Après la publication
- Onglet **Actions** : le workflow CI se lance et doit passer au vert (lint, types, tests, seuil de qualité F1).
- Réglages du dépôt → *About* : ajouter une description et des topics (`nlp`, `ocr`, `agentic-ai`, `llm`, `fastapi`, `document-processing`).
- Créer une *release* `v0.1.0` (onglet Releases).
- Épingler le dépôt sur ton profil GitHub et ajouter le lien sur ton CV / LinkedIn.

## 9. Comment présenter le projet (jury, recruteur)

**Pitch (20 s)** : « Un agent qui lit des documents techniques, en extrait les données structurées,
vérifie leur cohérence avec des règles métier et déclenche des actions (ticket, alerte, relecture) en
gardant des garde-fous quand un LLM décide. »

Points à mettre en avant :
- **Agent réel** : planification, outils validés par schéma, retries avec backoff, vérification
  après action, récupération sur échec (tests d'injection de pannes).
- **Garde-fous** : un défaut critique produit toujours un ticket, même si le LLM l'oublie.
- **Évaluation** : métriques P/R/F1 + jeu « difficile » qui montre les limites (tableaux, phrases libres)
  — assume-les, c'est un signe de rigueur.
- **Qualité logicielle** : types, 94 tests, CI, Docker, API documentée.

Démo suggérée (3 min) : `idp process data/samples` → ouvrir un rapport critique → montrer le ticket JSON →
`idp evaluate data/samples_hard` pour discuter les limites → feuille de route.

## 10. Idées d'extension (pour aller plus loin)

1. Extraction de **tableaux** (pdfplumber) et de mesures dans des **phrases** (spaCy `Matcher`) — comble les échecs du jeu difficile.
2. **Repli LLM** pour l'extraction quand la confiance est faible, revalidé par le moteur de règles.
3. Vrais connecteurs : Jira, e-mail (SMTP), Slack.
4. Jeu de test plus large avec de vraies fiches techniques publiques annotées ; mesurer le gain de chaque amélioration.

## 11. Problèmes fréquents

| Symptôme | Solution |
|---|---|
| `idp : commande introuvable` | Environnement non activé, ou utiliser `python -m idp_agent` |
| `Tesseract binary not found` | Installer Tesseract et l'ajouter au PATH (voir §2) ; les .txt/.pdf marchent sans |
| OCR : langue `fra` manquante | Installer le pack français ; sinon le projet se rabat sur l'anglais |
| `Scanned PDF detected: install pdf2image` | `pip install -e ".[ocr-pdf]"` + installer Poppler (PDF scannés uniquement) |
| `ModuleNotFoundError: fastapi` | `pip install -e ".[api]"` |
| `IDP_... is not a valid ...` | Variable d'environnement invalide, voir `.env.example` |
