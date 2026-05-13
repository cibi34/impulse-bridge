# Impulse Bridge — production image.
# Multi-arch: builds the same way on Oracle Cloud ARM (Ampere) and on x86_64.
FROM python:3.12-slim

# Non-root runtime user.
RUN useradd --create-home --shell /bin/bash --uid 10001 impulse

WORKDIR /app

# Copy source first so the install layer rebuilds when code changes. For POC
# scale this is acceptable; once dependencies stabilise, split into deps + code
# layers for better caching.
COPY pyproject.toml ./
COPY app ./app
COPY static ./static
COPY docs ./docs

RUN pip install --no-cache-dir --upgrade pip wheel && \
    pip install --no-cache-dir .

# Drop privileges. Bind-mounted host directories (configs/, data/) need to be
# readable/writable by uid 10001 — the deployment guide (docs/07-deployment.md,
# Step 6) instructs the operator to chown them after copying the source.
RUN chown -R impulse:impulse /app
USER impulse

EXPOSE 8080

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--proxy-headers", \
     "--forwarded-allow-ips=*"]
