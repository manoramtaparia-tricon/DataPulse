const trackingData = {
  'customer-data-platform': {
    title: 'C123 - Tracking Results',
    customerId: 'C123',
    projectTitle: 'Customer Data Platform',
    timeline: [
      {
        stage: 'Source',
        detail: 'customer_events',
        status: 'Found',
        timestamp: '2024-03-20 10:15',
        tone: 'success'
      },
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
        stage: 'Reconciliation',
        detail: 'waiting for account match',
        status: 'Stuck',
        timestamp: 'Waiting for account match',
        tone: 'warning'
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
        label: 'Run RCA Analysis',
        tone: 'primary'
      },
      {
        label: 'View Executed Queries',
        tone: 'secondary'
      }
    ]
  }
};

module.exports = { trackingData };
