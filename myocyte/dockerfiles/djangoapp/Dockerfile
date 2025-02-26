FROM ubuntu:24.04 

LABEL maintainer="Jente M Houweling"
LABEL affiliation="RIVM - National Institute for Public Health and the Environment,\
UM - Maastricht University"
LABEL email="Jente.Houweling@rivm.nl"
LABEL developer="Matthias ML Arras"
LABEL version="0.0.1"
LABEL last_update="2025-02-25"
# Add more stuff here if needed


# Set environment variables
ENV APP_HOME=/home/myocyte
ENV DATABASE=postgres
# NO INTERACTIVE
ENV DEBIAN_FRONTEND=noninteractive

# Prevents Python from writing pyc files (equivalent to python -B option): reduces the image size
ENV PYTHONDONTWRITEBYTECODE 1

# Prevents Python from buffering stdout and stderr (equivalent to python -u option)
ENV PYTHONUNBUFFERED 1
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
    texlive-luatex \
    pandoc \
    git \
    && rm -rf /var/lib/apt/lists/* 


    
RUN mkdir -p $APP_HOME
WORKDIR $APP_HOME

# Install python dependencies 
COPY requirements.txt $APP_HOME/requirements.txt
RUN python3 -m pip install --no-cache-dir --upgrade pip  --user  --break-system-packages
RUN python3 -m pip install --user --break-system-packages -r $APP_HOME/requirements.txt 

COPY . $APP_HOME

# setup folder strucutre
RUN mkdir -p $APP_HOME/logs && \
    touch $APP_HOME/logs/django_logfile.log && \
    # Location for file interchanges
    mkdir -p $APP_HOME/static && \
    mkdir -p $APP_HOME/media

RUN chmod +x $APP_HOME/django_startup.sh && chown root:root $APP_HOME/django_startup.sh
# Switch to the non-root user
USER root
ENTRYPOINT ["/home/myocyte/django_startup.sh"]