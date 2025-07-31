FROM ubuntu:24.04 

LABEL maintainer="Jente M Houweling"
LABEL affiliation="RIVM - National Institute for Public Health and the Environment,\
    UM - Maastricht University"
LABEL email="Jente.Houweling@rivm.nl"
LABEL developer="Matthias ML Arras"
ARG VERSION
# Add more stuff here if needed


# Set environment variables
ENV APP_HOME=/home/myocyte
ENV DATABASE=postgres
# NO INTERACTIVE
ENV DEBIAN_FRONTEND=noninteractive
# Tell poetry to create virtual environments in the project directory
ENV POETRY_VIRTUALENVS_CREATE=true \
    POETRY_VIRTUALENVS_IN_PROJECT=true

# Prevents Python from writing pyc files (equivalent to python -B option): reduces the image size
ENV PYTHONDONTWRITEBYTECODE=1
# Prevents Python from buffering stdout and stderr (equivalent to python -u option)
ENV PYTHONUNBUFFERED=1
ENV DEBUG=False

# Update and upgrade and install python and pip and pandoc
RUN apt-get update && apt-get upgrade -y && apt-get install --no-install-recommends -y \
    gcc \
    gunicorn \
    netcat-openbsd \ 
    libpq-dev \
    python3 \
    python3-pip \
    python3-dev \
    python3-venv \
    pipx \
    fontconfig \
    texlive-latex-base \
    texlive-science \
    texlive-luatex \
    fonts-texgyre \
    fonts-texgyre-math \
    pandoc \
    git \
    # for debuggin 
    net-tools \
    curl \
    # cleanup
    && rm -rf /var/lib/apt/lists/* 

# refresh lualatex font directories
RUN fc-cache -fv
RUN luaotfload-tool --update --force

# Install python dependencies 
# Expose pipx’s shims directory
ENV PATH="/root/.local/bin:${PATH}"

# Use pipx to install Poetry into its own venv
RUN pipx install poetry

ENV TESTING=${TESTING:-false}
ARG TESTING=${TESTING:-false}
# Print to sdtout for debugging purposes Testing
RUN echo "Testing mode is set to: ${TESTING}"

WORKDIR /home
COPY pyproject.toml poetry.lock ./

# 2) Install into that in-project venv
RUN if [ "$TESTING" = "true" ]; then \
    echo "🧪 TESTING mode: installing ALL deps (incl. dev)"; \
    poetry install --no-interaction; \
    else \
    echo "🚀 Production mode: installing only main deps"; \
    poetry install --no-interaction --without dev; \
    fi

# This is needed to ensure that the virtual environment is used by default
ENV PATH="/home/.venv/bin:${PATH}"

RUN mkdir -p $APP_HOME
WORKDIR $APP_HOME
COPY myocyte/ $APP_HOME

# setup folder strucutre
RUN mkdir -p $APP_HOME/logs && \
    touch $APP_HOME/logs/django_logfile.log && \
    # Location for file interchanges
    mkdir -p $APP_HOME/static && \
    mkdir -p $APP_HOME/media

# write git hash to the image
# This is useful for debugging and version control
# move as late as possible, will change every time so resets the cache layer
ARG GIT_HASH
ENV GIT_HASH=${GIT_HASH}

# Copy license so it can be auto converted to html with pandoc in the next step
COPY LICENSE $APP_HOME/toxtempass/templates/toxtempass/md_content/LICENSE.md
# run the python script md to html of all files in the md_content folder
RUN python3 $APP_HOME/toxtempass/templates/toxtempass/md_content/dependencies/run_pandoc.py

RUN chmod +x $APP_HOME/django_startup.sh && chown root:root $APP_HOME/django_startup.sh
# Switch to the non-root user
USER root
ENTRYPOINT ["/home/myocyte/django_startup.sh"]

LABEL version="${VERSION}"