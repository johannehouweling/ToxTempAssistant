#!/bin/sh
set -eu

echo "Waiting for MinIO to become available..."

# Wait until MinIO is reachable and admin creds work
until mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null 2>&1; do
  sleep 1
done

echo "MinIO is up. Initializing…"

# Create bucket (idempotent)
mc mb -p "local/$AWS_STORAGE_BUCKET_NAME" || true

# Create application user (idempotent)
mc admin user add local "$AWS_ACCESS_KEY_ID" "$AWS_SECRET_ACCESS_KEY" || true

# Create bucket-scoped policy
cat > /tmp/policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:*"],
      "Resource": [
        "arn:aws:s3:::$AWS_STORAGE_BUCKET_NAME",
        "arn:aws:s3:::$AWS_STORAGE_BUCKET_NAME/*"
      ]
    }
  ]
}
EOF

mc admin policy create local "${AWS_STORAGE_BUCKET_NAME}-policy" /tmp/policy.json || true
mc admin policy attach local "${AWS_STORAGE_BUCKET_NAME}-policy" --user "$AWS_ACCESS_KEY_ID" || true

echo "MinIO init done."