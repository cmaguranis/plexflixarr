1. Kometa: Use the run_end Webhook

Kometa has native support for completion webhooks. You can configure this in your global config.yml under the webhooks attribute.
YAML

webhooks:
  # This fires only when the entire Kometa run finishes successfully
  run_end: https://your-webhook-url.com/kometa-done
  # Highly recommended: separate hook for failures
  error: https://your-webhook-url.com/kometa-failed