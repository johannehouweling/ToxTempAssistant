# ToxTempAssistant 
LLM based web-app to assist users in drafting an annotated toxicity test method template (ToxTemp).

ToxTemp "was developed (i) to fulfill all requirements of GD211, (ii) to guide the user concerning the types of answers and detail of information required, (iii) >to include acceptance criteria for test elements, and (iv) to define the cells sufficiently and transparently." [1]

## TOC
- [ToxTempAssistant](#toxtempassistant)
  - [TOC](#toc)
  - [Spin up server with docker](#spin-up-server-with-docker)
    - [Get OpenAI API credentials](#get-openai-api-credentials)
    - [Azure AI Foundry — add a model](#azure-ai-foundry--add-a-model)
    - [Get ORCID iD credentials](#get-orcid-id-credentials)
    - [Create Certificate](#create-certificate)
    - [MinIO setup](#minio-setup)
  - [License](#license)
  - [Maintainer](#maintainer)
  - [References](#references)
  - [Contribute](#contribute)
    - [Poetry for Dependency Management](#poetry-for-dependency-management)
    - [Running Tests with Pytest](#running-tests-with-pytest)
    - [Ruff for Linting](#ruff-for-linting)
    - [Conventional Commits](#conventional-commits)
    - [Git Pre-Commit Hooks](#git-pre-commit-hooks)
    - [Pull Requests (PRs)](#pull-requests-prs)

## Spin up server with docker
We work with a `.env` file to store mission critical information and setups. These need to be set to match your local environment. In addition, please revise `myocyte/dockerfiles/nginx/nginx.conf` to the settings needed for your specific setup.

Modify and rename the '.env.dummy'-file to `.env` in same path as the `docker-compose.yml` with configuration data on server

- `DEBUG` settitng for django should be False for production
- `SECRET_KEY` for django, salt for pw hashes
- `OPENAI_API_KEY` for LLM access
- `ORCID_CLIENT_ID` and `ORCID_CLIENT_SECRECT` to facilitate login via ORCID (see below for details)
- `ALLOWED_HOSTS` URI of the app, and IP address of server, potentaially also furhter aliases
- `POSTGRES_HOST` IP address of dedicated Postgres server if available, otherwise postgres_for_django to use postgres included in docker compose (obviously, the postgres server can be taken out of the docker compose if an external server is used)
- `POSTGRES_PORT` Port of Postgres Server, usually 5432, also use 5432 for docker compose postgres
- `POSTGRES_USER` Postgres User, default 'postgres'
- `POSTGRES_PASSWORD` Password for user, needs to be set using psql (see below)
- `POSTGRES_DB` Database name for django to use, also postgres user needs to be granted permissions to said db (see below)
- `MINIO_ROOT_USER` MinIO *admin console* username (root/admin account).
- `MINIO_ROOT_PASSWORD` MinIO *admin console* password (root/admin account

The easier way to spin up the server is by using our docker compose file, if you are using an external PostGres Server, it is best to remove the postgres portion and its network from the docker-file. 
```bash
docker compose -f docker-compose.yml up
```

> **Note — BuildKit required.** The `djangoapp` image uses BuildKit-only
> features (cache mounts, `# syntax=` frontend pin) for faster rebuilds.
> BuildKit is the default in Docker 23.0+ / Compose v2. On older engines,
> enable it explicitly with `export DOCKER_BUILDKIT=1
> COMPOSE_DOCKER_CLI_BUILD=1` before running `docker compose build/up`.

### Get OpenAI API credentials
https://platform.openai.com/api-keys

### Azure AI Foundry — add a model

ToxTempAssistant can serve models from Azure AI Foundry (Azure OpenAI, Mistral,
Anthropic, Moonshot/Kimi, etc.) in parallel to (or instead of) the direct OpenAI
/ OpenRouter paths. Models are auto-discovered from the `.env` file at startup —
no code changes are required to add, remove, or retire a deployment.

#### Env-var convention

Each endpoint is numbered `E1`, `E2`, ... and carries three parts:

1. **Endpoint address + key** (once per endpoint):
   ```
   AZURE_E<n>_ENDPOINT=<base URL of the Azure resource>
   AZURE_E<n>_KEY=<API key>
   AZURE_E<n>_API_VERSION=<only for Azure OpenAI resources>
   ```
2. **Model deployment** (one triple per model on the endpoint):
   ```
   AZURE_E<n>_DEPLOY_<TAG>=<Azure deployment name>
   AZURE_E<n>_MODEL_<TAG>=<underlying model id>
   AZURE_E<n>_TAGS_<TAG>=<comma-separated key:value metadata>
   ```
3. **Metadata tags** are written as `key:value` pairs separated by commas. The
   following keys are recognised:

   | key | purpose | example |
   |---|---|---|
   | `tier` | Azure deployment tier | `regional` · `datazone` · `global` · `batch` |
   | `residency` | where data is actually processed | `eu` · `us` · `global` |
   | `provider` | who built the model | `openai` · `anthropic` · `mistral` · `moonshot` |
   | `direct-from-azure` | `true` = Microsoft-operated; `false` = third-party MaaS | `true` · `false` |
   | `version` | model version string | `2024-07-18` |
   | `api` | wire protocol | `openai` · `azure-openai` · `anthropic` · `foundry` |
   | `retirement-date` | ISO date when Azure deprecates the deployment | `2026-10-01` |
   | `default` | marks the bootstrap default used when no admin choice exists | `true` |

   The admin UI at `/admin/toxtempass/llmconfig/` uses these tags to render
   privacy badges, retirement warnings, and health-check results.

#### Picking the right `api:` tag

Azure Foundry serves different model families at different URL shapes:

| URL shape you see in the Azure portal | `api:` value |
|---|---|
| `…services.ai.azure.com/openai/v1/` | `openai` |
| `…cognitiveservices.azure.com/openai/deployments/<dep>/…?api-version=…` | `azure-openai` (needs `AZURE_E<n>_API_VERSION`) |
| `…services.ai.azure.com/models/chat/completions?api-version=…` | `openai` (OpenAI-compatible passthrough; the `?api-version=…` goes in the endpoint URL) |
| `…services.ai.azure.com/anthropic/…` | `anthropic` (strip the trailing `/v1/messages`) |

#### Example: add Azure OpenAI `gpt-4o-mini`

From Azure OpenAI Studio → Deployments → your deployment, copy the endpoint URL:

```
https://toxtempass-foundry.cognitiveservices.azure.com/openai/deployments/gpt-4o-mini/chat/completions?api-version=2025-01-01-preview
```

Then in `.env`:

```
AZURE_E1_ENDPOINT=https://toxtempass-foundry.cognitiveservices.azure.com/
AZURE_E1_API_VERSION=2025-01-01-preview
AZURE_E1_KEY=<your-key>

AZURE_E1_DEPLOY_GPT4OMINI=gpt-4o-mini
AZURE_E1_MODEL_GPT4OMINI=gpt-4o-mini
AZURE_E1_TAGS_GPT4OMINI=tier:datazone,residency:eu,provider:openai,direct-from-azure:true,version:2024-07-18,api:azure-openai,retirement-date:2026-10-01,default:true
```

`default:true` makes this deployment the fallback the app boots with when no
`LLMConfig` DB row exists yet (e.g. fresh deploys and CI). If more than one
model carries `default:true`, the first one wins and a warning is logged.

#### Verifying the wiring

The `test_llm_endpoints` management command pings every discovered deployment
with a trivial prompt and reports latency / errors. Add `--save` to persist the
results to `LLMConfig.last_health_check` so they show up in the admin panel.

```bash
docker compose exec djangoapp python manage.py test_llm_endpoints
docker compose exec djangoapp python manage.py test_llm_endpoints --only GPT4OMINI
docker compose exec djangoapp python manage.py test_llm_endpoints --save
```

The admin panel at `/admin/toxtempass/llmconfig/` also has a **Run health check
now** button that triggers the same checks synchronously and renders results in
a table alongside the data-handling (privacy) badges.

#### Removing / retiring a model

- **Soft retire**: add `retirement-date:YYYY-MM-DD` to the tag list. The admin
  table shows a countdown (⏳) when within 30 days, then marks the row greyed
  out and unselectable (☠️) once the date has passed. The model is also hidden
  from the user-facing picker automatically.
- **Hard remove**: delete the three `AZURE_E<n>_DEPLOY_<TAG>` /
  `AZURE_E<n>_MODEL_<TAG>` / `AZURE_E<n>_TAGS_<TAG>` lines from `.env` and
  restart the container.

### Get ORCID iD credentials
To obtain ORCID iD and secret perform the following steps:
- login to personal or institutional orcid
- then click on user-settings -> Developper Tools 
- Confirm Terms of Servicen and click 'Register for your ORCID Public API credentials'
- Fill in Application Name, Application URL, Application Description and Redirect URIs
- Application Name: ToxTempAssistant
- Application URL: URL e.g. https://toxtempass.mainlvldomain.nl
- Application Description (suggestion): ToxTemp, "an annotated toxicity test method template was developed (i) to fulfill all requirements of GD211, (ii) to guide the user concerning the types of answers and detail of information required, (iii) >to include acceptance criteria for test elements, and (iv) to define the cells sufficiently and transparently." (doi.org/10.14573/altex.1909271)
- Redirect URI: URL/orcid/callback/ e.g. https://toxtempass.mailvldomain.nl/orcid/callback/
   
### Create Certificate
Required for orcid login and general privacy considerations, it is advised to setup https. To this end a certificate is required. Create a Certificate Signing Request and send it to Certifying Authority, your institution should have someone. 
See this article, which also has some details on making the certificiate work with nginx: https://www.digitalocean.com/community/tutorials/how-to-create-a-self-signed-ssl-certificate-for-nginx-in-ubuntu-20-04-1

### MinIO setup
MinIO provides local S3-compatible object storage for the app.

- Set `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` in `.env` for the MinIO admin account.
- Set `MINIO_DJANGO_USER` and `MINIO_DJANGO_PASSWORD` in `.env` for the application access keys.
- Start the stack with `docker compose -f docker-compose.yml up` and open the MinIO console at `http://127.0.0.1:9001`.
- Log in with the root credentials, create a user for Django with the access keys above, and create the bucket(s) needed by your deployment.
- The MinIO API is available inside the Docker network on port `9000`; only the console is exposed to the host.

## License
This project is licensed under the GNU Affero General Public License, see the LICENSE file for details.

## Maintainer
- Jente Houweling | firstname.lastname@rivm.nl
- Matthias Arras | firstname.lastname@gmail.com
  
## References
[1]: Krebs, Alice, et al. "Template for the description of cell-based toxicological test methods to allow evaluation and regulatory use of the data." ALTEX-Alternatives to animal experimentation 36.4 (2019): 682-699. https://dx.doi.org/10.14573/altex.1909271

## Contribute

We welcome contributions! Here is how to get started and what our expectations are for contributors.

### Poetry for Dependency Management

This project uses [Poetry](https://python-poetry.org/) as the package manager.

- To install Poetry, run:
  ```
  conda install -c conda-forge pipx
  pipx ensurepath
  pipx install poetry
  ```

- To update dependencies and the lock file inside your virtual environment, run:
  ```
  poetry update
  ```

- No need to run `pip install -r requirements.txt`; Poetry manages dependencies and the lock file automatically.

### Running Tests with Pytest

We use [pytest](https://docs.pytest.org/en/stable/) along with `factory_boy`, `Faker`, and ephemeral database settings for testing.

- To run tests locally, navigate to the django `ROOT` (where `manage.py` is located), then:

  On Unix:
  ```shell
  cd myocyte
  export DJANGO_SETTINGS_MODULE=myocyte.settings  
  poetry run pytest
  ```

  On PowerShell:
  ```powershell
  cd myocyte
  $env:DJANGO_SETTINGS_MODULE="myocyte.settings"
  poetry run pytest
  ```
  (alternatively use `DJANGO_SETTINGS_MODULE=myocyte.myocyte.settings` if you run from project root, where `pyproject.toml` is).

- Tests are automatically run in GitHub Actions CI inside Docker to mirror production conditions as closely as possible.

- Only if all tests pass will we be able to proceed to include the PR.

### Ruff for Linting

We use [Ruff](https://github.com/charliermarsh/ruff) as the linter to keep the codebase consistent and clean.

- Run Ruff locally using Poetry or directly, for example:
  ```
  poetry run ruff check .
  ```

- You can automatically fix many linting issues by running:
  ```
  poetry run ruff check . --fix
  ```

### Conventional Commits

We follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification.

- Please format your commit messages accordingly to maintain readable and automated changelog generation.

- Example commit messages:
  - `feat: add new toxicity test endpoint`
  - `fix: correct calculation error in data normalization`
  - `docs: update README with contribution instructions`

### Git Pre-Commit Hooks

To help maintain code quality, we provide Git pre-commit hooks.

- Install the hooks by running:
  ```
  pip install pre-commit
  pre-commit install
  ```

- These hooks will automatically run Ruff and check your commit messages before allowing commits.

### Pull Requests (PRs)

- We encourage you to create Pull Requests for your contributions.

- On each PR, GitHub Actions will automatically run our CI workflow (`.github/workflows/ci.yml`) which builds the Docker image and runs the test suite.

- All tests must pass before the PR can be merged.

- Please include tests with any new features or bug fixes you contribute.

Thank you for helping make this project better!
