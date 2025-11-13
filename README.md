# k8s-eicar-test

A dead-simple web UI for uploading files (like the EICAR anti-malware test string) and writing them to disk so that downstream agents can observe or scan them. The repo contains a small Flask app, container definition, and Helm chart to run it inside Kubernetes.

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export UPLOAD_DIR=$PWD/uploads
python -m app.main
```

Then open <http://localhost:8080> and upload a file. Uploaded files are saved to the directory referenced by `UPLOAD_DIR`.

## Container build

```bash
docker build -t eicar-upload:local .
```

Run it locally:

```bash
docker run --rm -p 8080:8080 -e UPLOAD_DIR=/data/uploads -v $(pwd)/uploads:/data/uploads eicar-upload:local
```

## Helm deployment

The Helm chart lives in `charts/eicar-upload`.

1. (Optional) Push the image to a registry your cluster can reach.
2. Update `values.yaml` (or use `--set/--values`) with your image reference and any persistence tweaks.
3. Install:

   ```bash
   helm install eicar charts/eicar-upload \
     --set image.repository=REGISTRY/eicar-upload \
     --set image.tag=TAG
   ```

### Persistence options

By default the release uses an `emptyDir` volume. To keep uploads across pod restarts:

```bash
helm install eicar charts/eicar-upload \
  --set image.repository=REGISTRY/eicar-upload \
  --set image.tag=TAG \
  --set upload.persistence.enabled=true \
  --set upload.persistence.size=5Gi
```

Or plug in your own claim via `upload.persistence.existingClaim`.

### Ingress

Enable ingress and set the host/class that fit your cluster:

```bash
helm upgrade --install eicar charts/eicar-upload \
  --set ingress.enabled=true \
  --set ingress.className=nginx \
  --set ingress.hosts[0].host=eicar.example.com
```

### kubectl proxy alternative

If you only need temporary access (e.g., in a dev cluster without ingress), you can rely on the Kubernetes API server as a reverse proxy:

```bash
helm upgrade --install eicar charts/eicar-upload
kubectl proxy --port=8001
```

Then access the service through the proxied URL (adjust namespace if you installed somewhere other than `default`):

```
http://127.0.0.1:8001/api/v1/namespaces/default/services/http:eicar-eicar-upload:80/proxy/
```

This forwards requests through your local kubeconfig session without exposing any network listener inside the cluster.

### Clean up

```bash
helm uninstall eicar
```

## Helm chart values overview

Key knobs in `values.yaml`:

| Key | Description |
| --- | ----------- |
| `image.*` | Container image settings |
| `upload.path` | Path inside the container used to persist uploads |
| `upload.persistence.*` | Controls PVC creation / binding |
| `service.*` | ClusterIP/LoadBalancer type + port |
| `ingress.*` | Ingress setup (disabled by default) |
| `autoscaling.*` | Optional HPA configuration |
| `probes.*` | Liveness/readiness probe paths and timings |

## Testing the upload path

1. Install the chart.
2. Port-forward the service:
   ```bash
   kubectl port-forward svc/eicar-eicar-upload 8080:80
   ```
3. Open http://localhost:8080 and upload the [EICAR test file](https://www.eicar.org/download-anti-malware-testfile/).
4. Exec into the pod or inspect the mounted volume to confirm the file exists under `/data/uploads` (or your configured path).

### Uploading from the CLI (no browser required)

If you are on a headless server, you can still exercise the endpoint via `curl`. First create the EICAR sample locally, appending a timestamp to avoid name collisions:

```bash
STAMP=$(date +%Y%m%dT%H%M%S)
EICAR_FILE="eicar-${STAMP}.com"
cat <<'EOF' > "${EICAR_FILE}"
X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*
EOF
```

Then POST it to the service (replace `localhost:8080` with your port-forward, ingress host, or proxy URL):

```bash
curl -f -X POST \
  -F "file=@${EICAR_FILE}" \
  http://localhost:8080/upload
```

The server responds with the on-disk path, which you can later verify via `kubectl exec` or by inspecting the persistent volume.

### Verifying uploads in the cluster

1. **Find the pod** (adjust the label selector if you renamed the release):
   ```bash
   kubectl get pods -l app.kubernetes.io/name=eicar-upload
   POD=$(kubectl get pods -l app.kubernetes.io/name=eicar-upload -o jsonpath='{.items[0].metadata.name}')
   ```
2. **List uploaded files** inside the container (defaults to `/data/uploads` unless you changed `upload.path`):
   ```bash
   kubectl exec "$POD" -- ls -l /data/uploads
   ```
3. **Inspect the file contents or checksum** to confirm the payload:
   ```bash
   kubectl exec "$POD" -- sha256sum /data/uploads/eicar-<timestamp>.com
   # or
   kubectl exec "$POD" -- cat /data/uploads/eicar-<timestamp>.com
   ```
4. **If using a PVC**, you can also inspect the mounted claim from any other pod or via your storage backend’s tooling.

For local Docker testing with `-v $(pwd)/uploads:/data/uploads`, simply check the `uploads/` directory on your host.
