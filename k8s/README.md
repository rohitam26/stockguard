# StockGuard Kubernetes Starter Manifests

These manifests serve as educational reference configurations demonstrating how StockGuard's containerized API service can be packaged and deployed to a Kubernetes cluster (e.g., local development via Minikube/Kind or cloud-managed K8s).

> [!NOTE]
> These manifests are provided as educational architecture templates for portfolio and deployment study. They do not represent an active live production cluster.

## Included Manifests

- **`deployment.yaml`**: Configures a 2-replica Deployment of the FastAPI service with rolling update strategies, CPU/memory resource boundaries, and HTTP liveness and readiness health probes pointing to `/api/v1/health`.
- **`service.yaml`**: Exposes the application internally on port 8000 via a standard `ClusterIP` service.
- **`configmap.yaml`**: Centralizes non-sensitive runtime parameters such as event poll intervals, queue exchanges, and database pool limits.
- **`secrets-example.yaml`**: Template for credentials (PostgreSQL connection strings, RabbitMQ credentials) with secure placeholders.

## Applying Locally (Minikube / Kind)

```bash
# 1. Create a secret from the example template
kubectl apply -f k8s/secrets-example.yaml

# 2. Apply configmap
kubectl apply -f k8s/configmap.yaml

# 3. Deploy the application service and deployment
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```
