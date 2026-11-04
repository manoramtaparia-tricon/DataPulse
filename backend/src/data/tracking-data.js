const trackingData = {
  'customer-data-platform': {
    title: 'C123 - Tracking Results',
    customerId: 'C123',
    projectTitle: 'Customer Data Platform',
    timeline: [
      {
        stage: 'Bronze',
        detail: 'raw data',
        status: 'Found',
        timestamp: '2024-03-20 10:16',
        tone: 'success'
      },
      {
        stage: 'Silver',
        detail: 'cleaned data',
        status: 'Found',
        timestamp: '2024-03-20 10:30',
        tone: 'success'
      },
      {
        stage: 'Gold',
        detail: 'analytics ready',
        status: 'Not found',
        timestamp: '--',
        tone: 'muted'
      }
    ],
    summary: {
      status: 'STUCK',
      message: 'Customer C123 is stuck in the reconciliation stage as it is waiting for a matching account record.'
    },
    actions: [
      {
        id: 'run_rca',
        label: 'Run RCA Analysis',
        tone: 'primary'
      },
      {
        id: 'view_queries',
        label: 'View Executed Queries',
        tone: 'secondary'
      }
    ]
  }
};

const rcaData = {
  verdict: 'ROOT_CAUSE_IDENTIFIED',
  confidence: 'HIGH',
  category: 'ORPHAN_REFERENCE',
  failingStage: {
    fromLayer: 'Silver',
    toLayer: 'Reconciliation',
    table: 'reconciled_customers',
    transformation: 'INNER JOIN accounts ON customer_id'
  },
  summary: 'The customer record is held at reconciliation because no matching account record exists yet. This is a referential-integrity gap, not a pipeline failure: the latest pipeline run succeeded.',
  rootCause: 'No account row exists for this customer, so the reconciliation INNER JOIN drops it.',
  evidence: [
    { finding: '0 matching rows in accounts for this customer_id.', source: 'data_query', reference: 'accounts', observed_at: '2024-03-20 10:31' },
    { finding: 'The last reconciliation task run succeeded.', source: 'job_runs', reference: 'task reconcile', observed_at: '2024-03-20 10:30' }
  ],
  hypotheses: [
    { hypothesis: 'Reconciliation job has not run since ingestion.', confidence: 'LOW', supporting: null, contradicting: 'Last build is after ingestion.' }
  ],
  pipelineStatus: 'Latest run succeeded for all tasks; Silver and reconciliation are fresher than the record.',
  missingEvidence: [],
  nextChecks: ['Confirm whether the account source has a pending record for this customer.'],
  queries: [
    { sql: 'SELECT COUNT(*) FROM accounts WHERE customer_id = ...', row_count: 1, error: null }
  ]
};

module.exports = { trackingData, rcaData };
