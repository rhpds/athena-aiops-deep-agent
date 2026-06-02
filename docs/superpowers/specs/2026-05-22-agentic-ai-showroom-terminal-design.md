# Agentic AI Showroom Terminal Image Design

## Goal

Build a purpose-built showroom terminal image for the LB2645 Agentic DevOps lab that replaces the generic OCP showroom terminal with modern SRE/AI tooling matching the Kira ttyd experience, while staying compatible with showroom's deployment model.

## Context

The standard showroom terminal (`openshift-showroom-terminal-ocp`) ships Java/Maven, pipeline tools (tkn, kn), and other OpenShift-centric CLIs irrelevant to the agentic DevOps lab. The Kira ttyd container has the right tooling (bat, ripgrep, neovim, deepagents, uv/Python) but runs as a different user (`dev` uid 1001) with a custom entrypoint incompatible with showroom's deployment.

The fork at `https://github.com/rhpds/agentic-ai-showroom-terminal-image.git` provides the starting point — the upstream showroom terminal image repo structure with `Containerfile.base`, `Containerfile.ocp`, and the `assets/` directory (bashrc, runttyd, motd).

## Architecture

### Image Layering

```
Containerfile.base (UBI 10 + ttyd + tini + basic tools)
  └── Containerfile.agentic (SRE/AI tools + modern shell)
        └── Future: Containerfile.claude-code, Containerfile.deepagents, etc.
```

A single new `Containerfile.agentic` builds `FROM quay.io/rhpds/openshift-showroom-terminal-baseimage:latest`, following the same pattern as `Containerfile.ocp`. It keeps showroom's `lab-user`, `runttyd` entrypoint, and tini process supervisor.

Published to: `quay.io/rhpds/agentic-ai-showroom-terminal:latest` (+ date tag).

### Compatibility Contract

- User: `lab-user` (showroom convention)
- Entrypoint: tini → runttyd (showroom convention)
- Port: 7681 (ttyd default)
- Volume: `/home/lab-user` (showroom convention)
- First-boot setup: copies bashrc from `/var/lab-user/bashrc.base` (showroom convention)

## Tools

### Already in base image

ttyd, tini, vim, git, jq, tmux, skopeo, wget, unzip, procps, bash-completion, httpd-tools.

### Added by Containerfile.agentic

| Category | Tools | Source |
|----------|-------|--------|
| OpenShift CLIs | oc (stable-4.21), helm, virtctl, kubectl | Red Hat mirror, GitHub releases |
| Modern shell | bat, ripgrep | EPEL 10 |
| YAML | yq | GitHub release (mikefarah/yq) |
| Editor | neovim (latest stable) + LazyVim starter | GitHub release, LazyVim/starter |
| Python | uv, Python 3.13, deepagents, deepagents-cli, langchain-openai, awxkit | astral-sh/uv, PyPI |
| SSH | openssh-clients, sshpass | UBI 10 repos |

### Not included (stripped from OCP variant)

Java, Maven, odo, tkn, kn, roxctl, shp, pinentry, tzdata-java.

### Not included (future derivative images)

Claude Code (requires npm/node), pre-configured deepagents workspaces.

## Shell Experience

### Prompt

Colored SRE-style prompt matching Kira ttyd:

```
\[\e[32m\]sre\[\e[0m\]:\[\e[34m\]\w\[\e[0m\]$
```

Green `sre` label, blue working directory path.

### tmux Configuration

Provided as `assets/tmux.conf`, copied to `/home/lab-user/.tmux.conf`:

- vi mode keys
- Mouse support enabled
- `v` to start selection, `y` to copy
- Clipboard integration via pipe to xclip (works in ttyd)

### Bash Configuration

`assets/bashrc.agentic` is built as the file. The Containerfile copies it to `/var/lab-user/bashrc.base` inside the image, overriding the base image's version. This works because `runttyd` copies `/var/lab-user/bashrc.base` to `~/.bashrc` on first boot. Includes:

- Colored SRE prompt
- PATH additions: `/home/lab-user/.local/bin`, `/opt/deepagents/bin`
- bat aliases: `alias cat='bat --paging=never'`, `alias less='bat --paging=always'`
- Source all files in `~/.bashrc.d/` if the directory exists (derivative image hook)
- MOTD display

### MOTD

Updated MOTD for the agentic DevOps lab. The Containerfile copies `assets/motd.agentic` to `/etc/motd.d/rhdp`, overriding the base image's generic RHDP message:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Agentic DevOps Lab Terminal
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Tools: oc, helm, bat, yq, nvim, deepagents
  Python: 3.13 (uv) | Editor: neovim + LazyVim
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Neovim + LazyVim

LazyVim starter config cloned to `/home/lab-user/.config/nvim` at build time. Provides a modern editor out of the box with LSP, syntax highlighting, and file navigation.

### bashrc.d Directory Pattern

The `assets/bashrc.agentic` sources all files in `~/.bashrc.d/` if the directory exists. Derivative Containerfiles can drop additional bash config into this directory without modifying the base bashrc. The directory is created at build time in the Containerfile.

## Python Environment

uv installs Python 3.13 and creates a venv at `/opt/deepagents`:

- `deepagents` (library)
- `langchain-openai` (LLM integration)
- `awxkit` (AAP2 API client)

deepagents-cli installed via `uv tool install` for `lab-user`, lives at `/home/lab-user/.local/bin/deepagents`.

Permissions: `/root/.local/share/uv` and `/opt/deepagents` must be world-readable (same pattern as Kira ttyd). The root home dir needs `chmod a+x` for uv's Python install path traversal.

## Build & Publish

### build.sh Updates

Add a new build section for the agentic image:

```bash
IMAGE_NAME=quay.io/rhpds/agentic-ai-showroom-terminal
podman build . --file Containerfile.agentic \
  --platform linux/amd64 \
  --tag ${IMAGE_NAME}:latest
podman tag ${IMAGE_NAME}:latest ${IMAGE_NAME}:${BUILD_DATE}
podman push ${IMAGE_NAME}:latest
podman push ${IMAGE_NAME}:${BUILD_DATE}
```

Always build `--platform linux/amd64` for OpenShift.

### Deployment

In agnosticv, set the showroom terminal image:

```yaml
ocp4_workload_showroom_terminal_image: quay.io/rhpds/agentic-ai-showroom-terminal:latest
```

No changes needed to showroom's deployment role — it already accepts a configurable terminal image.

## File Changes Summary

### New files

| File | Purpose |
|------|---------|
| `Containerfile.agentic` | Main Containerfile for the agentic AI terminal |
| `assets/bashrc.agentic` | Bash config with colored prompt, bat aliases, bashrc.d sourcing |
| `assets/motd.agentic` | MOTD for agentic DevOps lab |
| `assets/tmux.conf` | tmux config with vi mode and mouse support |

### Modified files

| File | Change |
|------|--------|
| `build.sh` | Add agentic image build section |

### Unchanged files

`Containerfile.base`, `Containerfile.ocp`, `Containerfile.rosa`, `Containerfile.aro`, `assets/bashrc.base`, `assets/runttyd`, `assets/motd` — all upstream files left untouched.
