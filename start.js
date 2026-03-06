module.exports = {
  run: [
    { method: "shell.run", params: { message: "uv run python main.py serve", persistent: true } },
    { method: "browser.open", params: { url: "http://localhost:8000" } },
  ]
}
