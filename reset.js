module.exports = {
  run: [
    // Wipe all runtime-generated files
    { method: "shell.run", params: { message: "rm -f .env config.json run_stats.json event_agent.db event_agent.db-shm event_agent.db-wal" } },
    { method: "shell.run", params: { message: "rm -rf backups/" } },
    // Reset code to the latest clean version from origin
    { method: "shell.run", params: { message: "git fetch origin && git reset --hard origin/master && git clean -fd" } },
    // Reinstall dependencies
    { method: "shell.run", params: { message: "uv sync" } },
    { method: "shell.run", params: { message: "uv run playwright install chromium" } },
    // Reinitialise the database
    { method: "shell.run", params: { message: "uv run python main.py db init" } },
    // Restore the default local environment template
    { method: "fs.copy",   params: { src: ".env.local.example", dest: ".env", overwrite: true } },
  ]
}
