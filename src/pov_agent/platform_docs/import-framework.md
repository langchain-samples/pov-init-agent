# Importing your own framework

## When to use the Import Framework
Use **Tools & Frameworks → Import Framework** to bring an application or open-source tool that
isn't in the catalog (for example a custom RAG app, a vector database, or a chat UI) onto
the platform. Importing a framework requires the **Administrator** role.

## Packaging requirements
The framework must be packaged as a **Helm chart**, uploaded as a `.tgz` archive (`helm
package <chart-dir>`). For the app to be reachable through the platform's ingress, the
chart's `values.yaml` must include a `platform` section that defines an Istio virtual
service:

```yaml
platform:
  virtualService:
    endpoint: "myapp.${DOMAIN_NAME}"
    istioGateway: "istio-system/platform-gateway"
```

The platform substitutes `${DOMAIN_NAME}` at install time; the chart's templates must render
a `VirtualService` from these values.

## Import steps
1. Open **Tools & Frameworks** and click **Import Framework**.
2. Enter the framework name, description, category, and upload a logo.
3. Upload the Helm chart `.tgz` and set the **namespace** to install into.
4. Review or edit the `values.yaml`, then click **Submit**.

The framework then appears as a tile in Tools & Frameworks. Once its status is Ready, open it
at `https://myapp.<your-platform-domain>`.
