const { trackingData, rcaData } = require('../data/tracking-data');

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
    },
    // Mock tracking is always STUCK, so RCA is offered (mirrors the Python API contract).
    rca: {
      eligible: true,
      verdict: 'STUCK',
      reason: 'Found in Silver but not in Reconciliation.',
      context: { question, entity: { type: 'customer', id: customerId } }
    }
  };
}

function buildRcaResponse(context) {
  const customerId = (context && context.entity && context.entity.id) || 'C123';
  return {
    ...rcaData,
    title: `${customerId} - Root Cause Analysis`,
    entity: { type: 'customer', id: customerId }
  };
}

module.exports = {
  buildTrackingResponse,
  buildRcaResponse
};
