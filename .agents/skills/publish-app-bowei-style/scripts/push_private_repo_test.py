"""The parts of the private-repo helper that decide what may be published and how, without any network."""

import subprocess

import push_private_repo as helper
import pytest


@pytest.mark.parametrize("name", ["linkedin-inbox", "a", "my.app_2", "A-b"])
def test_ordinary_repo_names_are_accepted(name):
    assert helper.check_name(name) == name


@pytest.mark.parametrize(
    "name", ["", "-lead", "has space", "slash/inside", "semi;colon", None]
)
def test_other_repo_names_are_refused(name):
    with pytest.raises(helper.PublishError):
        helper.check_name(name)


def test_secret_and_data_paths_are_flagged_and_ordinary_ones_are_not():
    files = [
        "README.md",
        "src/app/runner.py",
        "docs/data-model.md",
        ".env",
        "deploy/.env.local",
        "data/.apps/app/raw/x.json",
        "x/.secrets/linkedin.env",
        "capture/request.env",
        "capture/request.json",
        "notes/cookie-handoff-invocations.json",
        "browser_state.json.enc",
        "credentials.json.enc",
        "src/app/metadata.py",
    ]

    assert helper.forbidden_files(files) == [
        ".env",
        "deploy/.env.local",
        "data/.apps/app/raw/x.json",
        "x/.secrets/linkedin.env",
        "capture/request.env",
        "capture/request.json",
        "notes/cookie-handoff-invocations.json",
        "browser_state.json.enc",
        "credentials.json.enc",
    ]


def test_a_new_repo_is_created_private_and_closed_to_outsiders():
    assert helper.create_payload("n", "d") == {
        "name": "n",
        "description": "d",
        "private": True,
    }
    lock = helper.lockdown_payload()
    assert lock["pull_request_creation_policy"] == "collaborators_only"
    assert not any(
        lock[key]
        for key in ("has_issues", "has_wiki", "has_projects", "has_discussions")
    )


def test_the_push_goes_through_the_gateway_and_its_password_is_never_printed():
    url = helper.gateway_url("http://127.0.0.1:1234/", "owner", "repo")
    command = helper.push_command("/src", url, "s3cret", override="any")

    assert url == "http://127.0.0.1:1234/gateway/https://github.com/owner/repo.git"
    assert command[-2:] == [url, "HEAD:refs/heads/main"]
    assert any("X-Latchkey-Gateway-Password: s3cret" in part for part in command)
    shown = " ".join(helper.redacted(command))
    assert (
        "s3cret" not in shown and "any" not in shown.split("Override:")[-1].split()[0]
    )
    assert "X-Latchkey-Gateway-Password: ***" in shown


def _repo(tmp_path, files):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t",
            "commit",
            "-qm",
            "first",
        ],
        check=True,
    )
    return str(tmp_path)


def test_a_dry_run_touches_nothing_and_a_dirty_source_is_refused(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("LATCHKEY_GATEWAY", "http://127.0.0.1:1")
    monkeypatch.setenv("LATCHKEY_GATEWAY_PASSWORD", "pw")
    clean = _repo(tmp_path / "clean", {"README.md": "hi"})
    dirty = _repo(tmp_path / "dirty", {"README.md": "hi", "data/x.json": "{}"})

    assert (
        helper.main(
            ["--name", "n", "--description", "d", "--source", clean, "--dry-run"]
        )
        == 0
    )
    assert "Nothing was done" in capsys.readouterr().out
    assert (
        helper.main(
            ["--name", "n", "--description", "d", "--source", dirty, "--dry-run"]
        )
        == 1
    )
    assert "data/x.json" in capsys.readouterr().err


def test_a_source_with_no_commit_is_refused(tmp_path, capsys):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)

    assert (
        helper.main(
            [
                "--name",
                "n",
                "--description",
                "d",
                "--source",
                str(tmp_path),
                "--dry-run",
            ]
        )
        == 1
    )
    assert (
        "no committed files" in capsys.readouterr().err
        or "commit" in capsys.readouterr().err
    )


def test_a_repo_answer_that_leaves_a_surface_open_is_reported():
    closed = {
        "has_issues": False,
        "has_wiki": False,
        "has_projects": False,
        "has_discussions": False,
    }

    assert helper.lockdown_gaps(closed) == []
    assert helper.lockdown_gaps({**closed, "has_projects": True}) == ["has_projects"]
    assert helper.lockdown_gaps({}) == [
        "has_issues",
        "has_wiki",
        "has_projects",
        "has_discussions",
    ]
