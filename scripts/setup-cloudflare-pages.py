#!/usr/bin/env python3
"""Connect a Git repository to Cloudflare Pages and optionally attach a domain.
Pushes to the production branch deploy automatically.
"""

import argparse
import getpass
import http.client
import json
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from typing import Self, cast
from urllib.parse import quote, urlparse

PROJECT_NAME_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,56}[a-z0-9])?")
ACCOUNT_ID_PATTERN = re.compile(r"[a-fA-F0-9]{32}")
DOMAIN_PATTERN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?")
SCP_GIT_URL_PATTERN = re.compile(r"^(?:[^@]+@)?(?P<host>[^:]+):(?P<path>.+)$")
REQUEST_TIMEOUT_SECONDS = 30


class SetupError(Exception):
    pass


@dataclass(frozen=True)
class ApiError:
    code: int | str
    message: str


@dataclass(frozen=True)
class ApiResponse:
    errors: tuple[ApiError, ...]
    result: object
    success: bool

    @classmethod
    def from_bytes(cls, payload: bytes) -> Self:
        try:
            decoded: object = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SetupError("Cloudflare returned a non-JSON response") from exc

        if not isinstance(decoded, dict):
            raise SetupError("Cloudflare returned an invalid JSON response")
        body = cast(dict[str, object], decoded)

        success = body.get("success")
        if not isinstance(success, bool):
            raise SetupError("Cloudflare response is missing a success value")

        raw_errors = body.get("errors", [])
        if not isinstance(raw_errors, list):
            raise SetupError("Cloudflare response contains invalid errors")

        errors: list[ApiError] = []
        for raw_error in raw_errors:
            if not isinstance(raw_error, dict):
                raise SetupError("Cloudflare response contains an invalid error")
            error = cast(dict[str, object], raw_error)
            code = error.get("code")
            message = error.get("message")
            if not isinstance(code, (int, str)) or not isinstance(message, str):
                raise SetupError("Cloudflare response contains an invalid error")
            errors.append(ApiError(code=code, message=message))

        return cls(
            errors=tuple(errors),
            result=body.get("result"),
            success=success,
        )

    def require_success(self, context: str) -> None:
        if self.success:
            return
        details = "; ".join(f"{error.code}: {error.message}" for error in self.errors)
        suffix = f": {details}" if details else ""
        raise SetupError(f"Cloudflare API failed {context}{suffix}")

    def object_result(self, context: str) -> dict[str, object]:
        if not isinstance(self.result, dict):
            raise SetupError(f"Cloudflare returned an invalid result {context}")
        return cast(dict[str, object], self.result)


@dataclass(frozen=True)
class GitRepository:
    name: str
    owner: str
    provider: str

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.name}"


class CloudflarePagesClient:
    def __init__(self, account_id: str, api_token: str) -> None:
        self._api_token = api_token
        self._projects_path = (
            f"/client/v4/accounts/{quote(account_id, safe='')}/pages/projects"
        )

    def request(
        self,
        method: str,
        path: str = "",
        body: dict[str, object] | None = None,
    ) -> tuple[int, ApiResponse]:
        data = None
        if body is not None:
            data = json.dumps(body, separators=(",", ":")).encode()

        connection = http.client.HTTPSConnection(
            "api.cloudflare.com", timeout=REQUEST_TIMEOUT_SECONDS
        )
        try:
            connection.request(
                method,
                f"{self._projects_path}{path}",
                body=data,
                headers={
                    "Authorization": f"Bearer {self._api_token}",
                    "Content-Type": "application/json",
                    "User-Agent": "textarea-cloudflare-setup/1",
                },
            )
            response = connection.getresponse()
            return response.status, ApiResponse.from_bytes(response.read())
        except (http.client.HTTPException, OSError) as exc:
            raise SetupError(f"could not reach Cloudflare: {exc}") from exc
        finally:
            connection.close()


def validate_inputs(
    account_id: str,
    project_name: str,
    production_branch: str,
    custom_domain: str | None,
) -> None:
    if ACCOUNT_ID_PATTERN.fullmatch(account_id) is None:
        raise SetupError(
            "account ID must be a 32-character hexadecimal Cloudflare account ID"
        )
    if PROJECT_NAME_PATTERN.fullmatch(project_name) is None:
        raise SetupError(
            "project name must be 1-58 lowercase letters, numbers, or hyphens, "
            "and cannot start or end with a hyphen"
        )
    if not production_branch or "\n" in production_branch or "\r" in production_branch:
        raise SetupError(
            "production branch must be nonempty and cannot contain a newline"
        )
    if custom_domain is not None and (
        DOMAIN_PATTERN.fullmatch(custom_domain) is None or "." not in custom_domain
    ):
        raise SetupError(
            "custom domain must be a hostname such as example.com or www.example.com"
        )


def require_interactive_terminal() -> None:
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        raise SetupError(
            "an interactive terminal is required to read the API token securely"
        )


def git_output(*arguments: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *arguments],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def parse_git_repository(remote_url: str) -> GitRepository:
    if "://" in remote_url:
        parsed = urlparse(remote_url)
        host = parsed.hostname
        path = parsed.path
    else:
        match = SCP_GIT_URL_PATTERN.fullmatch(remote_url)
        if match is None:
            raise SetupError(f"unsupported Git remote URL: {remote_url}")
        host = match.group("host")
        path = match.group("path")

    if host is None:
        raise SetupError(f"unsupported Git remote URL: {remote_url}")
    provider_by_host = {
        "github.com": "github",
        "gitlab.com": "gitlab",
    }
    provider = provider_by_host.get(host.lower())
    if provider is None:
        raise SetupError(
            "Cloudflare Pages Git integration supports github.com and gitlab.com; "
            f"the remote uses {host}"
        )

    normalized_path = path.strip("/")
    normalized_path = normalized_path.removesuffix(".git")
    path_parts = normalized_path.split("/")
    if len(path_parts) < 2 or any(not part for part in path_parts):
        raise SetupError(f"could not identify a repository from {remote_url}")

    return GitRepository(
        name=path_parts[-1],
        owner="/".join(path_parts[:-1]),
        provider=provider,
    )


def infer_git_repository(remote: str) -> GitRepository:
    repository_root = git_output("rev-parse", "--show-toplevel")
    if not repository_root:
        raise SetupError("run this script inside the Git repository to connect")
    remote_url = git_output("remote", "get-url", remote)
    if not remote_url:
        raise SetupError(
            f"Git remote '{remote}' does not exist or has no URL; pass --git-remote"
        )
    return parse_git_repository(remote_url)


def remote_branches(remote: str | None = None) -> set[str]:
    namespace = f"refs/remotes/{remote}" if remote is not None else "refs/remotes"
    output = git_output(
        "for-each-ref",
        "--format=%(refname:short)",
        namespace,
    )
    if not output:
        return set()

    branches: set[str] = set()
    for ref in output.splitlines():
        _, separator, branch = ref.partition("/")
        if separator and branch != "HEAD":
            branches.add(branch)
    return branches


def infer_production_branch(remote: str) -> str:
    remote_head = git_output(
        "symbolic-ref",
        "--quiet",
        "--short",
        f"refs/remotes/{remote}/HEAD",
    )
    if remote_head is not None:
        _, separator, branch = remote_head.partition("/")
        if separator and branch:
            return branch

    selected_remote_branches = remote_branches(remote)
    if len(selected_remote_branches) == 1:
        return selected_remote_branches.pop()

    all_branches = remote_branches()
    if len(all_branches) == 1:
        return all_branches.pop()

    raise SetupError(
        "could not infer one production branch from remote-tracking branches; "
        "pass --production-branch"
    )


def project_configuration(
    project_name: str,
    production_branch: str,
    repository: GitRepository,
) -> dict[str, object]:
    return {
        "build_config": {
            "build_command": "",
            "destination_dir": "public",
            "root_dir": "",
        },
        "name": project_name,
        "production_branch": production_branch,
        "source": {
            "config": {
                "owner": repository.owner,
                "pr_comments_enabled": True,
                "preview_deployment_setting": "all",
                "production_branch": production_branch,
                "production_deployments_enabled": True,
                "repo_name": repository.name,
            },
            "type": repository.provider,
        },
    }


def validate_project_source(
    result: dict[str, object],
    project_name: str,
    repository: GitRepository,
) -> None:
    raw_source = result.get("source")
    if not isinstance(raw_source, dict):
        raise SetupError(
            f"project '{project_name}' is a Direct Upload project and cannot be "
            "converted to Git integration; use a different --project-name"
        )
    source = cast(dict[str, object], raw_source)
    raw_config = source.get("config")
    if not isinstance(raw_config, dict):
        raise SetupError(f"project '{project_name}' has invalid Git configuration")
    config = cast(dict[str, object], raw_config)
    actual_repository = f"{config.get('owner')}/{config.get('repo_name')}"
    if (
        source.get("type") != repository.provider
        or actual_repository != repository.slug
    ):
        raise SetupError(
            f"project '{project_name}' is connected to {actual_repository}, "
            f"not {repository.slug}"
        )


def configure_project(
    client: CloudflarePagesClient,
    project_name: str,
    production_branch: str,
    repository: GitRepository,
) -> None:
    project_path = f"/{quote(project_name, safe='')}"
    status, response = client.request("GET", project_path)
    if status == 404:
        status, response = client.request(
            "POST",
            body=project_configuration(
                project_name,
                production_branch,
                repository,
            ),
        )
        response.require_success(f"while creating project '{project_name}'")
        if status not in {200, 201}:
            raise SetupError(
                f"Cloudflare returned unexpected HTTP {status} while creating project"
            )
        print(f"Connected Pages project to {repository.provider}: {repository.slug}")
        return

    if status != 200:
        response.require_success(
            f"while reading project '{project_name}' (HTTP {status})"
        )
        raise SetupError(
            f"Cloudflare returned unexpected HTTP {status} while reading project"
        )
    response.require_success(f"while reading project '{project_name}'")
    result = response.object_result(f"while reading project '{project_name}'")
    validate_project_source(result, project_name, repository)
    existing_branch = result.get("production_branch")
    if existing_branch != production_branch:
        raise SetupError(
            f"project '{project_name}' already exists with production branch "
            f"'{existing_branch}', not '{production_branch}'"
        )

    status, response = client.request(
        "PATCH",
        project_path,
        project_configuration(project_name, production_branch, repository),
    )
    response.require_success(f"while enabling Git deployments for '{project_name}'")
    if status != 200:
        raise SetupError(
            f"Cloudflare returned unexpected HTTP {status} while updating project"
        )
    print(f"Git deployments enabled: {repository.slug}")


def configure_domain(
    client: CloudflarePagesClient,
    project_name: str,
    custom_domain: str,
) -> None:
    project = quote(project_name, safe="")
    domain = quote(custom_domain, safe="")
    status, response = client.request("GET", f"/{project}/domains/{domain}")
    if status == 404:
        status, response = client.request(
            "POST",
            f"/{project}/domains",
            {"name": custom_domain},
        )
        response.require_success(f"while attaching custom domain '{custom_domain}'")
        if status not in {200, 201}:
            raise SetupError(
                f"Cloudflare returned unexpected HTTP {status} while attaching domain"
            )
        print(f"Attached custom domain: {custom_domain}")
        return

    if status != 200:
        response.require_success(
            f"while reading custom domain '{custom_domain}' (HTTP {status})"
        )
        raise SetupError(
            f"Cloudflare returned unexpected HTTP {status} while reading custom domain"
        )
    response.require_success(f"while reading custom domain '{custom_domain}'")
    result = response.object_result(f"while reading custom domain '{custom_domain}'")
    domain_status = result.get("status")
    print(f"Custom domain already attached: {custom_domain} ({domain_status})")


def run() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--account-id",
        required=True,
        help="non-secret 32-character Cloudflare account ID",
    )
    parser.add_argument(
        "--custom-domain",
        help="optional apex domain or subdomain to attach",
    )
    parser.add_argument(
        "--git-remote",
        default="origin",
        help="Git remote to connect (default: origin)",
    )
    parser.add_argument(
        "--production-branch",
        help="production branch; inferred from unambiguous remote Git refs by default",
    )
    parser.add_argument(
        "--project-name",
        help="Pages project name; defaults to the remote repository name",
    )
    args = parser.parse_args()
    repository = infer_git_repository(args.git_remote)
    project_name = args.project_name or repository.name
    production_branch = args.production_branch or infer_production_branch(
        args.git_remote
    )
    validate_inputs(
        args.account_id,
        project_name,
        production_branch,
        args.custom_domain,
    )
    require_interactive_terminal()
    api_token = getpass.getpass("Cloudflare API token: ")
    if not api_token:
        raise SetupError("API token cannot be empty")

    client = CloudflarePagesClient(args.account_id, api_token)
    configure_project(client, project_name, production_branch, repository)
    if args.custom_domain is not None:
        configure_domain(client, project_name, args.custom_domain)

    push_command = ["git", "push", args.git_remote, production_branch]
    print("\nSetup complete. Cloudflare will deploy pushes automatically.")
    print(f"Push the production branch with:\n  {shlex.join(push_command)}")
    dashboard_url = (
        f"https://dash.cloudflare.com/{quote(args.account_id, safe='')}"
        f"/pages/view/{quote(project_name, safe='')}"
    )
    print(f"\nCloudflare dashboard:\n{dashboard_url}")


def main() -> int:
    try:
        run()
    except SetupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print("\nCanceled.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
