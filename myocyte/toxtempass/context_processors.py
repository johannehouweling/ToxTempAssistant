from toxtempass import config


def github_repo_url(request):
    return {"GITHUB_REPO_URL": config.github_repo_url}
