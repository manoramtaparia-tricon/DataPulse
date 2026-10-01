const { trackingData } = require('../data/tracking-data');

function extractCustomerId(question) {
  const match = question.match(/customer\s+([a-z0-9-]+)/i);
  return match ? match[1].toUpperCase() : 'C123';
}

function buildTrackingResponse(projectTitle, question) {
  const customerId = extractCustomerId(question);
  const template = trackingData['customer-data-platform'];

  return {
    ...template,
    title: `${customerId} - Tracking Results`,
    customerId,
    projectTitle,
    question,
    summary: {
      ...template.summary,
      message: `Customer ${customerId} is stuck in the reconciliation stage as it is waiting for a matching account record.`
    }
  };
}

module.exports = {
  buildTrackingResponse
};
