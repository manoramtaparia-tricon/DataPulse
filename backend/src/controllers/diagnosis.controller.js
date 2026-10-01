const { buildTrackingResponse } = require('../services/diagnosis.service');

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

module.exports = {
  diagnose
};
