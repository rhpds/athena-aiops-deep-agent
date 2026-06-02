# Agentic AI Showroom Terminal Image Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a showroom-compatible terminal image with modern SRE/AI tooling (bat, ripgrep, neovim, uv/Python, deepagents) for the LB2645 Agentic DevOps lab.

**Architecture:** A new `Containerfile.agentic` builds FROM the existing showroom base image, adding agentic-specific tools and a polished shell experience. Four new asset files provide bash config, MOTD, and tmux config. The existing `build.sh` gets a new section for building and pushing the image.

**Tech Stack:** UBI 10, podman, ttyd, uv, Python 3.13, neovim/LazyVim

**Target repo:** `/tmp/agentic-ai-showroom-terminal-image/`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `assets/bashrc.agentic` | Create | Bash config: colored SRE prompt, PATH, bat aliases, bashrc.d sourcing, MOTD |
| `assets/motd.agentic` | Create | Agentic DevOps lab MOTD |
| `assets/tmux.conf` | Create | tmux config: vi mode, mouse, clipboard |
| `Containerfile.agentic` | Create | Main Containerfile: tools, Python, neovim, shell config |
| `build.sh` | Modify | Add agentic image build/push section |

---

### Task 1: Create shell assets (bashrc, motd, tmux.conf)

**Files:**
- Create: `assets/bashrc.agentic`
- Create: `assets/motd.agentic`
- Create: `assets/tmux.conf`

- [ ] **Step 1: Create `assets/bashrc.agentic`**

```bash
# .bashrc — Agentic DevOps Lab Terminal

# Source global definitions
if [ -f /etc/bashrc ]; then
        . /etc/bashrc
fi

# User specific environment
if ! [[ "$PATH" =~ "$HOME/.local/bin:$HOME/bin:" ]]; then
    PATH="$HOME/.local/bin:$HOME/bin:$PATH"
fi
export PATH="/opt/deepagents/bin:$PATH"

# Aliases — modern replacements
alias cat='bat --paging=never'
alias less='bat --paging=always'
alias ls="ls -F --color=auto"
alias la="ls -aF"
alias ll="ls -lF"

# Prompt — green user label, blue path
export PS1="\[\e[32m\]sre\[\e[0m\]:\[\e[34m\]\w\[\e[0m\]\$ "

# Source bashrc.d drop-ins (derivative image hook)
if [ -d ~/.bashrc.d ]; then
    for rc in ~/.bashrc.d/*; do
        if [ -f "$rc" ]; then
            . "$rc"
        fi
    done
fi
unset rc

# Print MotD
if [ -f /etc/motd.d/rhdp ]; then
    cat /etc/motd.d/rhdp
fi
```

Note: The `cat` in the MOTD line will resolve to the `bat` alias. Use `command cat` instead to avoid bat rendering the MOTD with syntax highlighting:

```bash
# Print MotD
if [ -f /etc/motd.d/rhdp ]; then
    command cat /etc/motd.d/rhdp
fi
```

- [ ] **Step 2: Create `assets/motd.agentic`**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Agentic DevOps Lab Terminal
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Tools: oc, helm, bat, yq, nvim, deepagents
  Python: 3.13 (uv) | Editor: neovim + LazyVim
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```

The trailing blank line ensures the prompt doesn't start immediately after the box.

- [ ] **Step 3: Create `assets/tmux.conf`**

```
# Enable vi mode
setw -g mode-keys vi

# Enable mouse support
set -g mouse on

# Start selection with 'v' and copy with 'y'
bind-key -T copy-mode-vi v send-keys -X begin-selection
bind-key -T copy-mode-vi y send-keys -X copy-selection-and-cancel

# Copy to system clipboard (Linux with xclip)
bind-key -T copy-mode-vi 'y' send -X copy-pipe-and-cancel 'xclip -in -selection clipboard'
bind-key -T copy-mode-vi Enter send -X copy-pipe-and-cancel 'xclip -in -selection clipboard'
bind-key -T copy-mode-vi MouseDragEnd1Pane send-keys -X copy-pipe-and-cancel 'xclip -in -selection clipboard'

# Paste from system clipboard
bind ] run "xclip -out -selection clipboard | tmux load-buffer - && tmux paste-buffer"

unbind-key -T root MouseDown3Pane
```

- [ ] **Step 4: Commit**

```bash
cd /tmp/agentic-ai-showroom-terminal-image
git add assets/bashrc.agentic assets/motd.agentic assets/tmux.conf
git commit -m "feat: add shell assets for agentic terminal (bashrc, motd, tmux)"
```

---

### Task 2: Create Containerfile.agentic

**Files:**
- Create: `Containerfile.agentic`

**Reference:** The file follows the same pattern as `Containerfile.ocp` — builds FROM the base image, runs as root to install tools, then switches back to `lab-user`.

- [ ] **Step 1: Create `Containerfile.agentic`**

```dockerfile
# -------------------------------------------------------------------
# Agentic AI Showroom Terminal Image
# Modern SRE/AI tooling for the LB2645 Agentic DevOps lab.
# -------------------------------------------------------------------
FROM --platform=linux/amd64 quay.io/rhpds/openshift-showroom-terminal-baseimage:latest

ARG OCP_VERSION="4.21"
ARG HELM_VERSION="latest"
ARG VIRTCTL_VERSION="v1.7.1"
ARG BUILD_DATE="2026-05-22"

LABEL maintainer="Tony Kay - ankay@redhat.com" \
      build-date=$BUILD_DATE

USER root

# ── EPEL (for bat, ripgrep) ──────────────────────────────────────
RUN dnf install -y \
      https://dl.fedoraproject.org/pub/epel/epel-release-latest-10.noarch.rpm && \
    dnf clean all

# ── System packages ─────────────────────────────────────────────
RUN dnf install -y --allowerasing \
      openssh-clients sshpass \
      bat ripgrep \
      curl bind-utils iputils nmap-ncat \
      && dnf clean all

# ── OC CLI ───────────────────────────────────────────────────────
RUN wget -q -O /tmp/oc.tar.gz \
      https://mirror.openshift.com/pub/openshift-v4/x86_64/clients/ocp/stable-${OCP_VERSION}/openshift-client-linux.tar.gz && \
    tar -C /usr/local/bin -zxvf /tmp/oc.tar.gz oc kubectl && \
    rm /tmp/oc.tar.gz

# ── Helm ─────────────────────────────────────────────────────────
RUN wget -q -O /usr/local/bin/helm \
      https://mirror.openshift.com/pub/openshift-v4/clients/helm/${HELM_VERSION}/helm-linux-amd64

# ── virtctl ──────────────────────────────────────────────────────
RUN wget -q -O /usr/local/bin/virtctl \
      https://github.com/kubevirt/kubevirt/releases/download/${VIRTCTL_VERSION}/virtctl-${VIRTCTL_VERSION}-linux-amd64

# ── yq ───────────────────────────────────────────────────────────
RUN curl -fsSL \
      https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 \
      -o /usr/local/bin/yq

# ── Neovim (latest stable) ──────────────────────────────────────
RUN curl -fsSL \
      https://github.com/neovim/neovim/releases/latest/download/nvim-linux-x86_64.tar.gz \
      | tar xzf - -C /opt && \
    ln -sf /opt/nvim-linux-x86_64/bin/nvim /usr/local/bin/nvim

# ── Fix permissions on all CLI tools ─────────────────────────────
RUN chown root:root /usr/local/bin/* && \
    chmod u=rwx,g=rwx,o=rx /usr/local/bin/*

# ── Bash completion for CLI tools ────────────────────────────────
RUN /usr/local/bin/oc completion bash >/etc/bash_completion.d/openshift && \
    /usr/local/bin/helm completion bash >/etc/bash_completion.d/helm && \
    /usr/local/bin/virtctl completion bash >/etc/bash_completion.d/virtctl

# ── uv + Python 3.13 + deepagents venv ──────────────────────────
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN uv python install 3.13 && \
    uv venv /opt/deepagents --python 3.13 && \
    VIRTUAL_ENV=/opt/deepagents uv pip install \
      deepagents langchain-openai awxkit && \
    chmod a+x /root && \
    chmod -R a+rX /root/.local/share/uv /opt/deepagents && \
    ln -sf /opt/deepagents/bin/python3 /usr/local/bin/python3.13

# ── Shell assets ─────────────────────────────────────────────────
COPY assets/bashrc.agentic /var/lab-user/bashrc.base
COPY assets/motd.agentic /etc/motd.d/rhdp
COPY assets/tmux.conf /home/lab-user/.tmux.conf

RUN chown lab-user:root /var/lab-user/bashrc.base /home/lab-user/.tmux.conf && \
    chmod u=rw,g=rw,o=r /var/lab-user/bashrc.base /home/lab-user/.tmux.conf && \
    chown root:root /etc/motd.d/rhdp && \
    chmod u=rx,g=rx,o=r /etc/motd.d/rhdp

# ── LazyVim for lab-user ─────────────────────────────────────────
RUN git clone https://github.com/LazyVim/starter /home/lab-user/.config/nvim && \
    rm -rf /home/lab-user/.config/nvim/.git && \
    chown -R lab-user:root /home/lab-user/.config

# ── bashrc.d directory (derivative image hook) ───────────────────
RUN mkdir -p /home/lab-user/.bashrc.d && \
    chown lab-user:root /home/lab-user/.bashrc.d

# ── deepagents-cli for lab-user ──────────────────────────────────
RUN su - lab-user -c "uv tool install deepagents-cli --python 3.13"

# ── Reset first-boot flag so runttyd copies new bashrc ───────────
RUN rm -f /home/lab-user/.setupcomplete

USER lab-user
```

**Key details:**
- `COPY assets/bashrc.agentic /var/lab-user/bashrc.base` overrides the base image's bashrc. The `runttyd` script copies this to `~/.bashrc` on first boot (when `.setupcomplete` doesn't exist).
- `rm -f /home/lab-user/.setupcomplete` ensures the new bashrc gets copied even if the base image left a stale flag.
- `chmod a+x /root` is needed so `lab-user` can traverse the uv python path at `/root/.local/share/uv/python/`.
- The image is always `--platform=linux/amd64` because OpenShift nodes are x86_64.

- [ ] **Step 2: Verify the Containerfile builds**

```bash
cd /tmp/agentic-ai-showroom-terminal-image
podman build . --file Containerfile.agentic \
  --platform linux/amd64 \
  --tag quay.io/rhpds/agentic-ai-showroom-terminal:latest
```

Expected: Build completes without errors. Look for:
- EPEL repo added successfully
- bat, ripgrep installed
- oc, helm, virtctl, yq downloaded
- neovim extracted to /opt
- uv installs Python 3.13
- deepagents venv created at /opt/deepagents
- deepagents-cli installed for lab-user
- LazyVim starter cloned

- [ ] **Step 3: Smoke-test the built image locally**

```bash
podman run --rm -it quay.io/rhpds/agentic-ai-showroom-terminal:latest bash -c "
  echo '--- CLI tools ---'
  oc version --client 2>&1 | head -1
  helm version --short 2>&1 | head -1
  virtctl version --client 2>&1 | head -1
  yq --version
  nvim --version | head -1
  bat --version | head -1
  rg --version | head -1
  echo '--- Python ---'
  python3.13 --version
  /opt/deepagents/bin/python3 -c 'import deepagents; print(\"deepagents OK\")'
  echo '--- deepagents-cli ---'
  which deepagents || echo 'deepagents-cli not in PATH (expected: /home/lab-user/.local/bin/deepagents)'
  ls /home/lab-user/.local/bin/deepagents 2>/dev/null && echo 'deepagents-cli binary exists'
  echo '--- Shell assets ---'
  cat /var/lab-user/bashrc.base | grep -c 'sre' && echo 'bashrc has SRE prompt'
  cat /etc/motd.d/rhdp | head -3
  cat /home/lab-user/.tmux.conf | grep -c 'vi' && echo 'tmux.conf has vi mode'
  ls /home/lab-user/.config/nvim/init.lua && echo 'LazyVim installed'
  ls -d /home/lab-user/.bashrc.d && echo 'bashrc.d directory exists'
"
```

Expected: All tools report versions, deepagents imports, shell assets are in place.

- [ ] **Step 4: Commit**

```bash
cd /tmp/agentic-ai-showroom-terminal-image
git add Containerfile.agentic
git commit -m "feat: add Containerfile.agentic with SRE/AI tooling"
```

---

### Task 3: Update build.sh

**Files:**
- Modify: `build.sh`

- [ ] **Step 1: Add agentic image build section to `build.sh`**

Insert the following block after the existing OCP image build section (after the OCP `podman push` calls, before the ROSA section). Find the line `# -------------------------------------------------------------------` that starts the ROSA section and insert before it:

```bash
# -------------------------------------------------------------------
# Build Agentic AI Showroom Terminal Image
# -------------------------------------------------------------------
VIRTCTL_VERSION="v1.7.1"
BUILD_DATE=$(date +"%Y-%m-%d")
IMAGE_NAME=quay.io/rhpds/agentic-ai-showroom-terminal

podman build . --file Containerfile.agentic \
  --platform linux/amd64 \
  --build-arg BUILD_DATE=${BUILD_DATE} \
  --build-arg VIRTCTL_VERSION=${VIRTCTL_VERSION} \
  --tag ${IMAGE_NAME}:latest

if [ $? -ne 0 ]; then
  echo "*******************************************************************************"
  echo "Error building image ${IMAGE_NAME}."
  echo "*******************************************************************************"

  exit
fi

podman tag ${IMAGE_NAME}:latest ${IMAGE_NAME}:${BUILD_DATE}
podman push ${IMAGE_NAME}:latest
podman push ${IMAGE_NAME}:${BUILD_DATE}

```

- [ ] **Step 2: Commit**

```bash
cd /tmp/agentic-ai-showroom-terminal-image
git add build.sh
git commit -m "feat: add agentic image to build.sh"
```

---

### Task 4: Build, push, and verify

**Files:** None (operational task)

- [ ] **Step 1: Build the final image**

```bash
cd /tmp/agentic-ai-showroom-terminal-image
podman build . --file Containerfile.agentic \
  --platform linux/amd64 \
  --tag quay.io/rhpds/agentic-ai-showroom-terminal:latest
```

- [ ] **Step 2: Push to quay.io**

```bash
podman push quay.io/rhpds/agentic-ai-showroom-terminal:latest
BUILD_DATE=$(date +"%Y-%m-%d")
podman tag quay.io/rhpds/agentic-ai-showroom-terminal:latest \
  quay.io/rhpds/agentic-ai-showroom-terminal:${BUILD_DATE}
podman push quay.io/rhpds/agentic-ai-showroom-terminal:${BUILD_DATE}
```

- [ ] **Step 3: Push git changes**

```bash
cd /tmp/agentic-ai-showroom-terminal-image
git push
```

- [ ] **Step 4: Update agnosticv to use the new image**

In the agnosticv worktree at `/Users/tok/Dropbox/PARAL/Resources/repos/agnosticv/worktrees/kira-frontend-0.11.1/summit-2026/lb2645-agentic-devops-tenant/common.yaml`, change the showroom terminal image. Find the line:

```yaml
ocp4_workload_showroom_terminal_image: quay.io/rhpds/openshift-showroom-terminal-ocp:2026-03-11
```

Replace with:

```yaml
ocp4_workload_showroom_terminal_image: quay.io/rhpds/agentic-ai-showroom-terminal:latest
```

Then commit and push:

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/agnosticv/worktrees/kira-frontend-0.11.1
git add summit-2026/lb2645-agentic-devops-tenant/common.yaml
PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -m "feat: switch showroom terminal to agentic-ai image"
git push
```

- [ ] **Step 5: Deploy a test tenant and verify**

Deploy a tenant from the agnosticv PR. Once deployed, open the Showroom Terminal tab and verify:
- MOTD shows "Agentic DevOps Lab Terminal"
- Prompt is green `sre:` with blue path
- `oc version --client` works
- `bat --version` works
- `nvim --version` works
- `python3.13 --version` works
- `deepagents --help` works
- `tmux` launches with mouse support
