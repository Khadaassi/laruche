#!/usr/bin/env bash
# Installation unique de l'infrastructure Google Cloud de La Ruche.
#
#   scripts/gcp-setup.sh <PROJECT_ID> [REGION]
#
# Prérequis : projet GCP existant avec facturation liée, `gcloud auth login`
# fait avec le bon compte, `gh auth login` fait. Relançable sans risque :
# chaque ressource n'est créée que si elle n'existe pas.
#
# Crée :
#   - le dépôt Docker Artifact Registry « laruche » (ne garde que 2 images) ;
#   - le compte de service d'exécution (lit les 2 secrets, rien d'autre) ;
#   - le compte de service de déploiement (utilisé par GitHub Actions) ;
#   - les secrets django-secret-key (généré) et database-url (demandé) ;
#   - la fédération d'identité GitHub → Google (aucune clé JSON), limitée
#     à la branche main de ce dépôt ;
#   - les variables GitHub lues par .github/workflows/deploy.yml.
set -euo pipefail

PROJECT_ID="${1:?Usage : scripts/gcp-setup.sh <PROJECT_ID> [REGION]}"
REGION="${2:-europe-west1}"
GITHUB_REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"

RUNTIME_SA="laruche-runtime@${PROJECT_ID}.iam.gserviceaccount.com"
DEPLOY_SA="laruche-deploy@${PROJECT_ID}.iam.gserviceaccount.com"
POOL="github"
PROVIDER="github"

gc() { gcloud --project "$PROJECT_ID" --quiet "$@"; }
step() { printf '\n==> %s\n' "$*"; }

PROJECT_NUMBER="$(gc projects describe "$PROJECT_ID" --format 'value(projectNumber)')"
SERVICE_HOST="laruche-${PROJECT_NUMBER}.${REGION}.run.app"

step "Activation des API"
gc services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com

step "Dépôt Artifact Registry"
if ! gc artifacts repositories describe laruche --location "$REGION" >/dev/null 2>&1; then
  gc artifacts repositories create laruche --repository-format docker --location "$REGION" \
    --description "Images de La Ruche"
fi
policy="$(mktemp)"
cat >"$policy" <<'JSON'
[
  {"name": "keep-2-recent", "action": {"type": "Keep"}, "mostRecentVersions": {"keepCount": 2}},
  {"name": "delete-others", "action": {"type": "Delete"}, "condition": {"tagState": "ANY"}}
]
JSON
gc artifacts repositories set-cleanup-policies laruche --location "$REGION" \
  --policy "$policy" --no-dry-run >/dev/null
rm -f "$policy"

step "Comptes de service"
for sa in laruche-runtime laruche-deploy; do
  if ! gc iam service-accounts describe "${sa}@${PROJECT_ID}.iam.gserviceaccount.com" >/dev/null 2>&1; then
    gc iam service-accounts create "$sa" --display-name "La Ruche (${sa#laruche-})"
  fi
done

step "Secrets"
if ! gc secrets describe django-secret-key >/dev/null 2>&1; then
  gc secrets create django-secret-key --replication-policy automatic
  python3 -c "import secrets; print(secrets.token_urlsafe(50), end='')" |
    gc secrets versions add django-secret-key --data-file -
fi
if ! gc secrets describe database-url >/dev/null 2>&1; then
  echo "URL Neon de PRODUCTION (branche principale, base laruche, pooling activé)."
  echo "Elle ne s'affiche pas pendant la saisie :"
  read -rs database_url
  echo
  [[ -n "$database_url" ]] || { echo "URL vide, abandon." >&2; exit 1; }
  gc secrets create database-url --replication-policy automatic
  printf '%s' "$database_url" | gc secrets versions add database-url --data-file -
  unset database_url
fi
for secret in django-secret-key database-url; do
  gc secrets add-iam-policy-binding "$secret" \
    --member "serviceAccount:${RUNTIME_SA}" --role roles/secretmanager.secretAccessor >/dev/null
done

step "Droits du compte de déploiement"
gc projects add-iam-policy-binding "$PROJECT_ID" \
  --member "serviceAccount:${DEPLOY_SA}" --role roles/run.admin --condition None >/dev/null
gc artifacts repositories add-iam-policy-binding laruche --location "$REGION" \
  --member "serviceAccount:${DEPLOY_SA}" --role roles/artifactregistry.writer >/dev/null
# Nécessaire pour lancer le service et le job sous l'identité d'exécution.
gc iam service-accounts add-iam-policy-binding "$RUNTIME_SA" \
  --member "serviceAccount:${DEPLOY_SA}" --role roles/iam.serviceAccountUser >/dev/null

step "Fédération d'identité GitHub"
if ! gc iam workload-identity-pools describe "$POOL" --location global >/dev/null 2>&1; then
  gc iam workload-identity-pools create "$POOL" --location global --display-name "GitHub Actions"
fi
if ! gc iam workload-identity-pools providers describe "$PROVIDER" \
  --workload-identity-pool "$POOL" --location global >/dev/null 2>&1; then
  gc iam workload-identity-pools providers create-oidc "$PROVIDER" \
    --workload-identity-pool "$POOL" --location global \
    --display-name "GitHub ${GITHUB_REPO}" \
    --issuer-uri "https://token.actions.githubusercontent.com" \
    --attribute-mapping "google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
    --attribute-condition "assertion.repository == '${GITHUB_REPO}' && assertion.ref == 'refs/heads/main'"
fi
POOL_ID="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}"
gc iam service-accounts add-iam-policy-binding "$DEPLOY_SA" \
  --role roles/iam.workloadIdentityUser \
  --member "principalSet://iam.googleapis.com/${POOL_ID}/attribute.repository/${GITHUB_REPO}" >/dev/null

step "Variables GitHub (${GITHUB_REPO})"
gh variable set GCP_PROJECT_ID --body "$PROJECT_ID"
gh variable set GCP_REGION --body "$REGION"
gh variable set GCP_WIF_PROVIDER --body "${POOL_ID}/providers/${PROVIDER}"
gh variable set GCP_DEPLOY_SA --body "$DEPLOY_SA"
gh variable set GCP_RUNTIME_SA --body "$RUNTIME_SA"
gh variable set DJANGO_ALLOWED_HOSTS --body "$SERVICE_HOST"

step "Terminé"
echo "Adresse de l'app : https://${SERVICE_HOST}/"
echo "Premier déploiement : gh workflow run deploy.yml (ou merge sur main)."
