# Access, login, and roles

## Logging in to Nimbus Workbench
Users open Nimbus Workbench at the URL their administrator shares, or from the **Nimbus
Console** by clicking **Launch** on the Workbench tile. Login uses single sign-on (SSO)
through the identity provider the platform administrator connected (for example, an
OIDC/SAML provider). There is no separate Workbench password.

## Roles
Nimbus Workbench has two built-in user roles:
- **Administrator** — manages users, resource quotas, data sources, the Tools & Frameworks
  catalog (including imported frameworks), and cluster settings.
- **Member** — the default role for data scientists, ML engineers, and analysts. Members can
  create notebook servers, run jobs and pipelines, track experiments in MLflow, use
  configured data sources, and deploy models with Model Serving within their quota.

Seniority or job title does not change what a Member can do; capabilities come only from
the assigned role and the quota the administrator sets.

## Requesting more access
If a task needs Administrator rights (for example importing a framework or adding a data
source), ask a platform administrator to perform it or to grant the role.
