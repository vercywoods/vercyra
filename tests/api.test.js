const test = require('node:test');
const assert = require('node:assert/strict');
const request = require('supertest');

const { createApp } = require('../server');

function createMockDb() {
  const state = {
    assessments: [],
    findings: [],
  };

  const db = {
    async query(sql, params = []) {
      if (sql.includes('SELECT NOW()')) {
        return { rows: [{ current_time: new Date().toISOString() }] };
      }

      if (sql.includes('CREATE TABLE IF NOT EXISTS')) {
        return { rows: [] };
      }

      if (sql.includes('INSERT INTO security_assessments')) {
        const id = state.assessments.length + 1;
        const record = {
          id,
          title: params[0],
          description: params[1],
          assessment_type: params[2],
          status: params[3],
          owner: params[4],
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };

        state.assessments.push(record);
        return { rows: [record], rowCount: 1 };
      }

      if (sql.includes('INSERT INTO vulnerability_findings')) {
        const rows = [];

        for (let index = 0; index < params.length; index += 7) {
          const assessmentId = params[index];
          const title = params[index + 1];
          const severity = params[index + 2];
          const description = params[index + 3];
          const remediation = params[index + 4];
          const location = params[index + 5];
          const evidence = params[index + 6];

          const record = {
            id: state.findings.length + 1,
            assessment_id: assessmentId,
            title,
            severity,
            description,
            remediation,
            location,
            evidence,
            created_at: new Date().toISOString(),
          };

          state.findings.push(record);
          rows.push(record);
        }

        return { rows, rowCount: rows.length };
      }

      if (sql.includes('FROM security_assessments')) {
        if (sql.includes('WHERE id =')) {
          const id = Number(params[0]);
          const record = state.assessments.find((item) => item.id === id);
          return { rows: record ? [record] : [], rowCount: record ? 1 : 0 };
        }

        return {
          rows: state.assessments.map((assessment) => ({
            ...assessment,
            finding_count: state.findings.filter((finding) => finding.assessment_id === assessment.id).length,
          })),
        };
      }

      if (sql.includes('FROM vulnerability_findings WHERE assessment_id =')) {
        const id = Number(params[0]);
        const records = state.findings.filter((finding) => finding.assessment_id === id);
        return { rows: records, rowCount: records.length };
      }

      return { rows: [], rowCount: 0 };
    },

    async connect() {
      return {
        async query(sql, params = []) {
          return db.query(sql, params);
        },
        async release() {
          return null;
        },
      };
    },
  };

  return db;
}

test('GET /health returns service status', async () => {
  const app = createApp({ pool: createMockDb() });
  const response = await request(app).get('/health');

  assert.equal(response.status, 200);
  assert.equal(response.body.status, 'ok');
  assert.equal(response.body.service, 'vercyra-api');
});

test('GET /health/db returns database status', async () => {
  const app = createApp({ pool: createMockDb() });
  const response = await request(app).get('/health/db');

  assert.equal(response.status, 200);
  assert.equal(response.body.database, 'connected');
  assert.ok(response.body.current_time);
});

test('POST /api/assessments accepts valid data and persists findings', async () => {
  const app = createApp({ pool: createMockDb() });
  const response = await request(app)
    .post('/api/assessments')
    .send({
      title: 'Quarterly review',
      description: 'Read-only assessment for a customer environment',
      assessment_type: 'web_application',
      status: 'completed',
      owner: 'security-team',
      findings: [
        {
          title: 'Outdated dependency',
          severity: 'medium',
          description: 'One dependency is behind the supported version.',
          location: 'package.json',
          remediation: 'Upgrade to the current supported version.',
          evidence: 'Audit report',
        },
      ],
    });

  assert.equal(response.status, 201);
  assert.equal(response.body.data.title, 'Quarterly review');
  assert.equal(response.body.data.findings.length, 1);
  assert.equal(response.body.data.findings[0].severity, 'medium');
});

test('POST /api/assessments rejects invalid requests', async () => {
  const app = createApp({ pool: createMockDb() });
  const response = await request(app)
    .post('/api/assessments')
    .send({
      title: '',
      assessment_type: '',
      findings: ['invalid'],
    });

  assert.equal(response.status, 400);
  assert.equal(response.body.error, 'Invalid assessment payload');
  assert.ok(Array.isArray(response.body.details));
});

test('GET /api/assessments returns stored records', async () => {
  const db = createMockDb();
  const app = createApp({ pool: db });

  await request(app)
    .post('/api/assessments')
    .send({
      title: 'Initial assessment',
      description: 'Example review',
      assessment_type: 'network',
      status: 'draft',
      owner: 'ops',
      findings: [],
    });

  const response = await request(app).get('/api/assessments');

  assert.equal(response.status, 200);
  assert.equal(response.body.data.length, 1);
  assert.equal(response.body.data[0].title, 'Initial assessment');
});
