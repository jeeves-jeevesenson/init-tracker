# Production Update Runbook

This document describes the general procedure for updating the production server.

## Security and Compliance

- **Developer Approval Required**: All production updates must be approved by the developer.
- **Agent Constraints**: Agents must not deploy, restart services, or push code unless explicitly instructed by the developer in a specific task.
- **Sensitive Information**: Never include passwords, SSH keys, tokens, private keys, or other secrets in tracked documentation.
- **Environment Details**: Specific hostnames, IP addresses, and account details belong in the gitignored `docs/local/production_environment.md` file, not here.

## Pre-update Checklist

1. **Verify Branch**: Ensure the current branch and commit have been tested and approved in the development environment.
2. **Backups**: Create a backup of the current production application directory before applying any changes.
3. **Validation**: Plan for bounded validation on the production server after the update.

## Update Procedure

1. **Push Approved Branch**: Push the tested and approved branch from the development environment to the remote repository.
2. **SSH to Production**: (Developer only or as explicitly directed) Log in to the production server.
3. **Backup Production**:
   ```bash
   cp -r /home/init-tracker/app /home/init-tracker/releases/predeploy-$(date +%Y%m%d-%H%M%S)
   ```
4. **Fetch and Checkout**:
   ```bash
   git fetch origin
   git checkout <approved-branch>
   ```
5. **Validation**: Run project-specific validation commands (e.g., `scripts/agent_gate_validate.sh`).
6. **Restart Service**:
   - Identify and stop the old process (e.g., `serve_headless.py` on port 8787).
   - Start the application using the production virtual environment and `nohup`.
   ```bash
   nohup /home/init-tracker/venv/bin/python3 serve_headless.py --host 0.0.0.0 --port 8787 > /home/init-tracker/logs/server.log 2>&1 &
   ```
7. **Verify**: Check the listener and logs to ensure the server started successfully.

## Post-update

- **Browser Smoke**: Browser-based smoke testing is the responsibility of the developer.
- **Monitoring**: Monitor logs for any immediate errors.
