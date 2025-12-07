# Cloud Run Resource Configuration

## Backend Service

### Current Configuration
- **CPU**: 8 cores
- **Memory**: 32GiB
- **Timeout**: 300 seconds (5 minutes)
- **Max Instances**: 10
- **Port**: 8000

### Configuration Location
The configuration is set in `cloud-run/deploy-enhanced.sh` in the `deploy_backend()` function:

```bash
gcloud run deploy knowledge-navigator-backend \
    --cpu 8 \
    --memory 32Gi \
    ...
```

## Frontend Service

### Current Configuration
- **CPU**: 1 core
- **Memory**: 512Mi
- **Timeout**: 300 seconds (5 minutes)
- **Max Instances**: 10

## Notes

- **CPU**: Cloud Run supports up to 8 CPUs per instance
- **Memory**: Cloud Run supports up to 32GiB per instance
- **Scaling**: Both services auto-scale based on request volume
- **Costs**: Higher resources = higher costs, but better performance

## Updating Resources

To change resource allocation, edit `cloud-run/deploy-enhanced.sh`:

1. **Backend**: Edit lines ~356-357 in `deploy_backend()` function
2. **Frontend**: Edit lines ~480-481 in `deploy_frontend()` function

Then redeploy:
```bash
./cloud-run/deploy-enhanced.sh backend
```

## Cost Considerations

- **32GiB Memory + 8 CPU**: Higher tier pricing, best for heavy workloads
- Consider monitoring usage and adjusting if over-provisioned
- Use Cloud Run metrics to optimize resource allocation

