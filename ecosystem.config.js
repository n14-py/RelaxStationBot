module.exports = {
  apps: [
    {
      name: "stream-core",
      script: "start.sh",
      autorestart: true,
      watch: false
    },
    {
      name: "web-server",
      script: "server.js",
      autorestart: true,
      watch: false,
      env: {
        PORT: 10000
      }
    }
  ]
};
