# Guide de Contribution & Stratégie de Branches (Git Workflow)

Ce projet applique une politique stricte de gestion de branches basée sur un tronc unique (**Trunk-based with short-lived feature branches**) :

---

## 1. Règle Fondamentale : `main` comme Branche Unique Permanente

- La branche `main` est l'unique branche pérenne du projet.
- **Aucune branche permanente `dev` ou intermédiaire** n'est conservée.

---

## 2. Cycle de Développement d'une Fonctionnalité / Correctif

Chaque évolution, correctif ou ajout suit obligatoirement le cycle suivant :

1. **Partir de la dernière version de `main`** :
   ```bash
   git checkout main
   git pull origin main
   ```

2. **Création d'une branche de travail éphémère et descriptive** :
   ```bash
   git checkout -b feat/<nom-court-descriptif>
   # ou fix/<nom-du-bug>, docs/<sujet>, refactor/<perfs>
   ```

3. **Validation continue & boucle stricte de vérification** :
   Avant tout merge, la branche doit être 100% verte :
   ```bash
   uv run ruff check .
   uv run mypy src/
   uv run mkdocs build --strict
   uv run pytest
   ```

4. **Merge sur `main` et suppression de la branche éphémère** :
   ```bash
   git checkout main
   git merge feat/<nom-court-descriptif>
   git push origin main
   git branch -d feat/<nom-court-descriptif>
   ```

---

## 3. Conventions de Commits

Nous respectons la convention [Conventional Commits](https://www.conventionalcommits.org/) :
- `feat(...)`: Nouvelle fonctionnalité
- `fix(...)`: Correction de bogue
- `docs(...)`: Documentation
- `test(...)`: Ajout ou ajustement de tests
- `refactor(...)`: Restructuration de code sans modification fonctionnelle
