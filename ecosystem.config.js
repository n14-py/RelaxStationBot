module.exports = {
  apps: [
    {
      name: "stream-bot",
      script: "python3 -u main.py",
      watch: true,
      ignore_watch: ["node_modules", "videos", "thumbs"],
    },
    {
      name: "web-server",
      script: "server.js",
      watch: true,
      ignore_watch: ["node_modules"],
    }
  ]
}
