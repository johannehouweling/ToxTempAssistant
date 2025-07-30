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

RUN mkdir -p $APP_HOME
WORKDIR $APP_HOME

# Install python dependencies 
# Expose pipx’s shims directory
ENV PATH="/root/.local/bin:${PATH}"

# Use pipx to install Poetry into its own venv
RUN pipx install poetry

# Configure Poetry and install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction

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