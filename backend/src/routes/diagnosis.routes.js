const { diagnose, rca } = require('../controllers/diagnosis.controller');

function registerDiagnosisRoutes(app) {
  app.post('/api/diagnose', diagnose);
  app.post('/api/rca', rca);
}

module.exports = {
  registerDiagnosisRoutes
};
