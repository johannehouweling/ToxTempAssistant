from toxtempass import config


def github_repo_url(request):
    return {"GITHUB_REPO_URL": config.github_repo_url}


def github_hash(request):
    return {"GIT_HASH": config.github_hash}

def maintainer_email(request):
    return {"MAINTAINER_EMAIL": config.maintainer_email}