const { diagnose } = require('../controllers/diagnosis.controller');

function registerDiagnosisRoutes(app) {
  app.post('/api/diagnose', diagnose);
}

module.exports = {
  registerDiagnosisRoutes
};
