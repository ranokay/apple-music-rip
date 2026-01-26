const api = Bun.spawn(["bun", "--watch", "server/index.ts"], {
  stdout: "inherit",
  stderr: "inherit",
});

const ui = Bun.spawn(["bun", "run", "dev:ui"], {
  stdout: "inherit",
  stderr: "inherit",
});

const shutdown = () => {
  try {
    api.kill();
  } catch {
    // ignore
  }
  try {
    ui.kill();
  } catch {
    // ignore
  }
  process.exit(0);
};

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
