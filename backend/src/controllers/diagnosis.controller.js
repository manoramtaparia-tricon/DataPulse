const { buildTrackingResponse, buildRcaResponse } = require('../services/diagnosis.service');

async function diagnose(req, res) {
  try {
    const question = String(req.body.question || '').trim();
    const projectTitle = String(req.body.projectTitle || 'Customer Data Platform');

    await new Promise((resolve) => setTimeout(resolve, 2000));

    res.status(200).json(buildTrackingResponse(projectTitle, question));
  } catch (error) {
    res.status(500).json({
      message: 'Unable to generate the diagnosis response.'
    });
  }
}

async function rca(req, res) {
  try {
    const context = req.body && req.body.context;

    if (!context || !context.entity) {
      res.status(422).json({ message: 'RCA is not applicable: no tracking context was provided.' });
      return;
    }

    await new Promise((resolve) => setTimeout(resolve, 2000));

    res.status(200).json(buildRcaResponse(context));
  } catch (error) {
    res.status(500).json({
      message: 'Unable to complete the root cause analysis.'
    });
  }
}

module.exports = {
  diagnose,
  rca
};
