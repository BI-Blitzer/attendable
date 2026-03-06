module.exports = {
  run: [
    { method: "shell.run", params: { message: "git pull" } },
    { method: "shell.run", params: { message: "uv sync" } },
    { method: "shell.run", params: { message: "uv run python main.py db init" } },
  ]
}
