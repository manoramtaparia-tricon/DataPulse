const { createApp } = require('./config/app');

const port = process.env.PORT || 3001;

const app = createApp();

app.listen(port, () => {
  console.log(`DataPulse backend listening on http://localhost:${port}`);
});
