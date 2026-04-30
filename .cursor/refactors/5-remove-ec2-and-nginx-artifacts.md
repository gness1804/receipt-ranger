---
github_issue: 67
---
# Remove leftover EC2/nginx deployment artifacts

## Working directory

`~/Desktop/receipt-ranger`

## Contents

The repo still contains files from the previous AWS EC2 + nginx deployment, which is no longer in use. The application now runs on Render (see `.cursor/progress/10-DONE-render-migration-handoff.md`), and the EC2 instance has been terminated.

The leftover artifacts include:

- `deploy.sh` at the repo root — a Bash script that previously handled EC2 deploys
- `deploy/` directory — nginx config and other EC2-era setup files
- A historical mention in `README.md` (around line 224) referencing these files

None of these are referenced by the current Render-based deployment (`Dockerfile`, `.streamlit/config.toml`, env vars in Render dashboard).

We should remove these so the repo no longer carries dead deployment infrastructure. Anyone returning to this codebase later (or scanning for unused code) will find it cleaner without the historical EC2 baggage. If we ever need to reference the EC2 setup again, it remains accessible in git history and on the `feature/aws-deployment` branch.

## Acceptance criteria

- `deploy.sh` deleted from repo root
- `deploy/` directory deleted
- `README.md` historical mention of EC2/nginx (around the "deployment" section) removed or simplified to a single sentence pointing at git history
- All tests still pass
- No remaining references to `deploy.sh` or the `deploy/` directory in the codebase (verify with `grep`)
- Confirm the App Runner-related branch (`refactor/ec2-to-app-runner`) and `feature/aws-deployment` branch are preserved if anyone needs to refer back; do not delete those branches as part of this work
