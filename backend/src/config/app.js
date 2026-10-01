const http = require('http');
const { registerDiagnosisRoutes } = require('../routes/diagnosis.routes');

function createApp() {
  const routes = [];

  const app = {
    use() {},
    post(path, handler) {
      routes.push({ method: 'POST', path, handler });
    },
    listen(port, callback) {
      const server = http.createServer((req, res) => {
        const matchingRoute = routes.find((route) => route.method === req.method && route.path === req.url.split('?')[0]);

        res.status = (statusCode) => {
          res.statusCode = statusCode;
          return res;
        };

        res.json = (payload) => {
          res.setHeader('Content-Type', 'application/json');
          res.setHeader('Access-Control-Allow-Origin', '*');
          res.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
          res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
          res.end(JSON.stringify(payload));
        };

        if (req.method === 'OPTIONS') {
          res.writeHead(204, {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
          });
          res.end();
          return;
        }

        if (!matchingRoute) {
          res.writeHead(404, {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
          });
          res.end(JSON.stringify({ message: 'Not found.' }));
          return;
        }

        let body = '';

        req.on('data', (chunk) => {
          body += chunk;
        });

        req.on('end', () => {
          try {
            req.body = body ? JSON.parse(body) : {};
            matchingRoute.handler(req, res);
          } catch (error) {
            res.writeHead(400, {
              'Content-Type': 'application/json',
              'Access-Control-Allow-Origin': '*'
            });
            res.end(JSON.stringify({ message: 'Invalid JSON body.' }));
          }
        });
      });

      return server.listen(port, callback);
    }
  };

  registerDiagnosisRoutes(app);
  return app;
}

module.exports = {
  createApp
};
