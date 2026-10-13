const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const { Pool } = require('pg');
const { z } = require('zod');
const dotenv = require('dotenv');

dotenv.config();

const DEFAULT_PORT = 3001;
const DEFAULT_CORS_ORIGINS = ['http://localhost:3000', 'http://localhost:5173'];

function parseAllowlist(value) {
  if (!value) {
    return DEFAULT_CORS_ORIGINS;
  }

  return value
    .split(',')
    .map((origin) => origin.trim())
    .filter(Boolean);
}

function createLogger() {
  return {
    info(message, metadata = {}) {
      console.log(JSON.stringify({ level: 'info', timestamp: new Date().toISOString(), message, ...metadata }));
    },
    warn(message, metadata = {}) {
      console.warn(JSON.stringify({ level: 'warn', timestamp: new Date().toISOString(), message, ...metadata }));
    },
    error(message, metadata = {}) {
      console.error(JSON.stringify({ level: 'error', timestamp: new Date().toISOString(), message, ...metadata }));
    },
  };
}

const logger = createLogger();

const findingSchema = z.object({
  title: z.string().trim().min(1).max(255),
  severity: z.enum(['low', 'medium', 'high', 'critical']).default('medium'),
  description: z.string().trim().min(1).max(5000),
  remediation: z.string().trim().max(2000).optional().nullable().transform((value) => value && value.trim() ? value.trim() : null),
  location: z.string().trim().max(255).optional().nullable().transform((value) => value && value.trim() ? value.trim() : null),
  evidence: z.string().trim().max(2000).optional().nullable().transform((value) => value && value.trim() ? value.trim() : null),
});

const assessmentSchema = z.object({
  title: z.string().trim().min(1).max(255),
  description: z.string().trim().max(5000).default(''),
  assessment_type: z.string().trim().min(1).max(100),
  status: z.enum(['draft', 'in_progress', 'completed', 'archived']).default('draft'),
  owner: z.string().trim().max(255).optional().nullable().transform((value) => value && value.trim() ? value.trim() : null),
  findings: z.array(findingSchema).max(100).default([]),
});

function createPool(connectionString = process.env.DATABASE_URL) {
  if (!connectionString) {
    return null;
  }

  return new Pool({
    connectionString,
    max: 10,
    ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false,
    application_name: 'vercyra-api',
  });
}

let defaultPool = createPool();

async function createTables(db) {
  const schema = `
    CREATE TABLE IF NOT EXISTS security_assessments (
      id SERIAL PRIMARY KEY,
      title VARCHAR(255) NOT NULL,
      description TEXT NOT NULL DEFAULT '',
      assessment_type VARCHAR(100) NOT NULL,
      status VARCHAR(30) NOT NULL DEFAULT 'draft',
      owner VARCHAR(255),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS vulnerability_findings (
      id SERIAL PRIMARY KEY,
      assessment_id INTEGER NOT NULL REFERENCES security_assessments(id) ON DELETE CASCADE,
      title VARCHAR(255) NOT NULL,
      severity VARCHAR(20) NOT NULL DEFAULT 'medium',
      description TEXT NOT NULL,
      remediation TEXT,
      location VARCHAR(255),
      evidence TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
  `;

  await db.query(schema);
}

function createApp({ pool = defaultPool || createPool() } = {}) {
  const app = express();
  const corsAllowlist = parseAllowlist(process.env.CORS_ORIGINS);

  app.disable('x-powered-by');
  app.use(
    helmet({
      crossOriginResourcePolicy: false,
      contentSecurityPolicy: {
        directives: {
          defaultSrc: ["'self'"],
        },
      },
    }),
  );

  app.use(
    cors({
      origin(origin, callback) {
        if (!origin) {
          return callback(null, true);
        }

        if (corsAllowlist.includes(origin)) {
          return callback(null, true);
        }

        logger.warn('Blocked request from disallowed origin', { origin });
        return callback(new Error('Origin not allowed by CORS policy'));
      },
      credentials: true,
      methods: ['GET', 'POST', 'OPTIONS'],
      allowedHeaders: ['Content-Type', 'Authorization'],
    }),
  );

  app.use(express.json({ limit: '1mb' }));

  app.use((req, res, next) => {
    const start = Date.now();

    res.on('finish', () => {
      logger.info('Request completed', {
        method: req.method,
        url: req.originalUrl,
        statusCode: res.statusCode,
        durationMs: Date.now() - start,
      });
    });

    next();
  });

  app.get('/health', (req, res) => {
    res.json({
      status: 'ok',
      timestamp: new Date().toISOString(),
      service: 'vercyra-api',
    });
  });

  app.get('/health/db', async (req, res) => {
    try {
      const result = await pool.query('SELECT NOW() AS current_time');
      res.json({
        status: 'ok',
        database: 'connected',
        current_time: result.rows[0].current_time,
      });
    } catch (error) {
      logger.error('Database health check failed', { message: error.message });
      res.status(503).json({
        status: 'error',
        database: 'disconnected',
        message: 'Database unavailable',
      });
    }
  });

  app.get('/api/assessments', async (req, res, next) => {
    try {
      const result = await pool.query(
        `
          SELECT
            a.id,
            a.title,
            a.description,
            a.assessment_type,
            a.status,
            a.owner,
            a.created_at,
            a.updated_at,
            COUNT(f.id) AS finding_count
          FROM security_assessments a
          LEFT JOIN vulnerability_findings f ON f.assessment_id = a.id
          GROUP BY a.id
          ORDER BY a.created_at DESC
        `,
      );

      res.json({ data: result.rows.map((row) => ({ ...row, finding_count: Number(row.finding_count || 0) })) });
    } catch (error) {
      next(error);
    }
  });

  app.post('/api/assessments', async (req, res, next) => {
    try {
      const result = assessmentSchema.safeParse(req.body);

      if (!result.success) {
        return res.status(400).json({
          error: 'Invalid assessment payload',
          details: result.error.issues.map((issue) => ({
            path: issue.path.join('.') || 'payload',
            message: issue.message,
          })),
        });
      }

      const assessment = result.data;
      const client = await pool.connect();

      try {
        await client.query('BEGIN');

        const assessmentInsert = await client.query(
          `
            INSERT INTO security_assessments (title, description, assessment_type, status, owner)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, title, description, assessment_type, status, owner, created_at, updated_at
          `,
          [assessment.title, assessment.description, assessment.assessment_type, assessment.status, assessment.owner],
        );

        const insertedAssessment = assessmentInsert.rows[0];

        const findings = assessment.findings.map((finding) => ({
          assessment_id: insertedAssessment.id,
          title: finding.title,
          severity: finding.severity,
          description: finding.description,
          remediation: finding.remediation,
          location: finding.location,
          evidence: finding.evidence,
        }));

        if (findings.length > 0) {
          const valueClauses = findings
            .map(
              (_, index) =>
                `($${index * 7 + 1}, $${index * 7 + 2}, $${index * 7 + 3}, $${index * 7 + 4}, $${index * 7 + 5}, $${index * 7 + 6}, $${index * 7 + 7})`,
            )
            .join(', ');

          const params = findings.flatMap((finding) => [
            finding.assessment_id,
            finding.title,
            finding.severity,
            finding.description,
            finding.remediation,
            finding.location,
            finding.evidence,
          ]);

          await client.query(
            `INSERT INTO vulnerability_findings (assessment_id, title, severity, description, remediation, location, evidence) VALUES ${valueClauses}`,
            params,
          );
        }

        const findingsResult = await client.query(
          `SELECT id, assessment_id, title, severity, description, remediation, location, evidence, created_at FROM vulnerability_findings WHERE assessment_id = $1 ORDER BY created_at ASC`,
          [insertedAssessment.id],
        );

        await client.query('COMMIT');

        res.status(201).json({
          data: {
            ...insertedAssessment,
            findings: findingsResult.rows,
          },
        });
      } catch (error) {
        await client.query('ROLLBACK');
        throw error;
      } finally {
        client.release();
      }
    } catch (error) {
      next(error);
    }
  });

  app.get('/api/assessments/:id', async (req, res, next) => {
    try {
      const assessmentId = Number(req.params.id);

      if (!Number.isInteger(assessmentId)) {
        return res.status(400).json({ error: 'Assessment id must be an integer' });
      }

      const assessmentResult = await pool.query(
        `SELECT id, title, description, assessment_type, status, owner, created_at, updated_at FROM security_assessments WHERE id = $1`,
        [assessmentId],
      );

      if (assessmentResult.rowCount === 0) {
        return res.status(404).json({ error: 'Assessment not found' });
      }

      const findingsResult = await pool.query(
        `SELECT id, assessment_id, title, severity, description, remediation, location, evidence, created_at FROM vulnerability_findings WHERE assessment_id = $1 ORDER BY created_at ASC`,
        [assessmentId],
      );

      res.json({
        data: {
          ...assessmentResult.rows[0],
          findings: findingsResult.rows,
        },
      });
    } catch (error) {
      next(error);
    }
  });

  app.use((req, res) => {
    res.status(404).json({ error: 'Not found' });
  });

  app.use((error, req, res, next) => {
    logger.error('Unhandled API error', {
      message: error.message,
      url: req.originalUrl,
      method: req.method,
    });

    if (res.headersSent) {
      return next(error);
    }

    res.status(500).json({
      error: 'Internal server error',
    });
  });

  return app;
}

async function startServer() {
  if (!process.env.DATABASE_URL) {
    logger.error('Database configuration missing', { message: 'DATABASE_URL is not configured' });
    process.exitCode = 1;
    return;
  }

  defaultPool = createPool();
  const app = createApp({ pool: defaultPool });

  try {
    await createTables(defaultPool);
    logger.info('Database schema ready');
  } catch (error) {
    logger.error('Failed to initialize database schema', { message: error.message });
    process.exitCode = 1;
    return;
  }

  const port = Number(process.env.PORT) || DEFAULT_PORT;

  app.listen(port, '0.0.0.0', () => {
    logger.info('Server started', {
      port,
      host: '0.0.0.0',
    });
  });

  process.on('SIGINT', async () => {
    logger.warn('Received SIGINT, shutting down gracefully');
    await defaultPool.end();
    process.exit(0);
  });

  process.on('SIGTERM', async () => {
    logger.warn('Received SIGTERM, shutting down gracefully');
    await defaultPool.end();
    process.exit(0);
  });
}

if (require.main === module) {
  startServer();
}

module.exports = {
  createApp,
  createTables,
  createPool,
  assessmentSchema,
  findingSchema,
};
