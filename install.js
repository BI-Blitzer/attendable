module.exports = {
  run: [
    // Install uv — try conda first (Pinokio default), fall back to pip
    { method: "shell.run", params: { message: "conda install -c conda-forge uv -y || pip install uv" } },
    // Install project dependencies
    { method: "shell.run", params: { message: "uv sync" } },
    // Install Chromium for Meetup and Eventbrite scrapers
    { method: "shell.run", params: { message: "uv run playwright install chromium" } },
    // Initialize the database
    { method: "shell.run", params: { message: "uv run python main.py db init" } },
    // Copy env template if .env doesn't exist yet
    { method: "fs.copy",   params: { src: ".env.local.example", dest: ".env", overwrite: false } },
  ]
}
